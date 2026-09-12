"""Sổ ngân sách nguyên tử cho gateway provider — LEDGER-01 (#43).

Quyết định: docs/LEDGER_OPTIONS.md (Astra chốt 12/09/2026: P1–P3, L1–L16 và tám
điều kiện bắt buộc). Sổ là mảnh **mở khoá đường tới mạng**: `authorize_dispatch`
(#41) từ chối gửi khi không có sổ, nên mọi thứ ở đây đứng giữa người dùng và tiền
thật.

Ba luật xuyên suốt:

1. **Giữ tiền và claim snapshot là một transaction.** `reserve_locked` không tự mở
   và không tự commit: nó nhận vé `_Tx` của `authorize_dispatch`. Tách ra là hai
   tiến trình cùng lọt (đo trên Data1000, SNAPSHOT_CONTRACT mục 3.4).
2. **Số nguyên micro-USD, làm tròn lên** (L1). Không `float`, không `bool` thay số.
3. **Không đoán.** Thiếu rate card, hết hạn, sai tiền tệ, chưa xác minh cận trên,
   sổ hỏng, đồng hồ lùi → chặn. Hạn mức mặc định 0 chặn mọi thứ (L5).

Module này không mở DB, không chọn đường dẫn, không gọi mạng và không đọc tệp nào
ngoài tệp cấu hình riêng máy do backend chỉ đường. MCP và model không có đường vào.
"""
import hashlib
import json
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from . import provider_snapshot as ps
from .provider_snapshot import SnapshotError, SnapshotView, canonical_json

MICRO = 1_000_000                       # micro-USD trong 1 USD; cũng là 1 triệu token
VN_OFFSET_MS = 7 * 60 * 60 * 1000       # L6: UTC+7 cố định, Việt Nam không đổi giờ mùa hè
DISPATCH_DEADLINE_MS = 60 * 1000        # PSC-01 mục 6: hạn chót một request
RECOVERY_GRACE_MS = 5 * 60 * 1000       # L10/L14: chỉ recover sau deadline bền vững
CLOCK_BACK_TOLERANCE_MS = 5 * 60 * 1000 # L14
CLOCK_FORWARD_MAX_MS = 24 * 60 * 60 * 1000
MIN_RESERVE_MICRO_USD = 1               # L5: v1 luôn giữ ít nhất 1 micro-USD
RATE_CARD_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000   # PSC-01: expires_at ≤ 7 ngày kể từ verified_at

# Chặn tràn: SQLite SUM cộng trên INTEGER 64 bit. MAX_AMOUNT × MAX_ROWS = 1e18 < 2^63.
MAX_AMOUNT_MICRO_USD = 10**12           # 1 triệu USD cho một attempt
MAX_ROWS = 10**6
MAX_TOKENS = 10**9
MAX_UNIT_PRICE = 10**12
MAX_EVIDENCE = 500

RATE_CARD_SCHEMA = "aimarx.rate_card/1"
LIMITS_SCHEMA = "aimarx.budget_limits/1"
# L2/L3: chỉ nhận cận trên đã được adapter xác minh trên TOÀN BỘ đầu vào provider tính phí.
# Tokenizer byte-level một mình chưa chứng minh phụ phí khung, nên phải có cả ba cờ.
VERIFIED_BOUND_METHODS = frozenset({"byte-level-verified"})

_HEX32 = re.compile(r"[0-9a-f]{32}")
_STATES = ("reserved", "settled", "released", "unresolved", "reconciled", "over_reserve")
_STATES_SQL = ",".join(f"'{s}'" for s in _STATES)
# Trạng thái còn buộc tiền vào request: chặn đường finish công khai (điều kiện 2).
PENDING_STATES = ("reserved", "unresolved", "over_reserve")

_MESSAGES = {
    "BUDGET_EXCEEDED": "Vượt hạn mức chi đã đặt",
    "PRICING_UNVERIFIED": "Bảng giá thiếu, hết hạn hoặc chưa được xác minh",
    "PROVIDER_LOCKED": "Nhà cung cấp đang bị khoá vì còn khoản chi chưa đối soát",
    "LEDGER_UNAVAILABLE": "Sổ ngân sách đang bận hoặc không dùng được; thử lại sau",
    "INVALID_REQUEST": "Yêu cầu không hợp lệ",
}


class LedgerError(SnapshotError):
    """Lỗi có mã công khai; không bao giờ mang payload, token, khoá hay nội dung nguồn."""

    def __init__(self, code, reason):
        ValueError.__init__(self, f"{code}: {_MESSAGES.get(code, 'Lỗi sổ ngân sách')}")
        self.code = code
        self.reason = reason


def _unavailable(reason):
    return LedgerError("LEDGER_UNAVAILABLE", reason)


def _invalid(reason):
    return LedgerError("INVALID_REQUEST", reason)


def _is_int(value, low, high):
    # `type(...) is int` loại bool (True là int trong Python) và mọi lớp con. L1.
    return type(value) is int and low <= value <= high


def _is_str(value, low, high):
    return type(value) is str and low <= len(value) <= high


def _amount(value):
    return _is_int(value, 0, MAX_AMOUNT_MICRO_USD)


# ---------- tiền ----------

def _ceil_div(numerator, denominator):
    return -(-numerator // denominator)


def price_micro_usd(entry, *, input_tokens, output_tokens):
    """R = ceil((I × P_in + O × P_out) / 1.000.000) + phí cố định mỗi request (L1).

    Toàn bộ là số nguyên: không có bước nào đi qua `float`. Mọi thừa số đã bị chặn
    trên nên tích không bao giờ ra ngoài dải đã kiểm.
    """
    if not _is_int(input_tokens, 0, MAX_TOKENS) or not _is_int(output_tokens, 0, MAX_TOKENS):
        raise _invalid("TOKENS")
    total = _ceil_div(input_tokens * entry["input_micro_usd_per_mtok"]
                      + output_tokens * entry["output_micro_usd_per_mtok"], MICRO)
    total += entry["request_fee_micro_usd"]
    if not _amount(total):
        raise _invalid("AMOUNT_RANGE")
    return total


def input_bound_tokens(entry, *, payload_size, message_count):
    """Cận trên số token đầu vào (L2).

    Chỉ đúng khi adapter đã xác minh rằng tokenizer là byte-level **và** phụ phí khung
    phủ toàn bộ đầu vào provider tính phí (system, schema, framing, biến đổi transport).
    `_validate_rate_card` đã chặn mọi entry không mang đủ ba bằng chứng đó, nên tới đây
    chỉ còn phép cộng. Số byte là cận đúng về toán, không phải ước lượng "ký tự / 4".
    """
    if not _is_int(payload_size, 0, MAX_TOKENS) or not _is_int(message_count, 0, 4096):
        raise _invalid("BOUND_INPUT")
    bound = (payload_size
             + message_count * entry["bound_overhead_tokens_per_message"]
             + entry["bound_overhead_tokens_fixed"])
    if not _is_int(bound, 0, MAX_TOKENS):
        raise _invalid("BOUND_RANGE")
    return bound


# ---------- rate card và hạn mức: tệp riêng máy, không nằm trong Git (L4, L5) ----------

_ENTRY_KEYS = frozenset({
    "provider", "model", "endpoint", "currency",
    "input_micro_usd_per_mtok", "output_micro_usd_per_mtok", "request_fee_micro_usd",
    "bound_method", "bound_overhead_tokens_per_message", "bound_overhead_tokens_fixed",
    "billable_inputs_verified", "output_includes_reasoning_cap",
    "verified_at_ms", "expires_at_ms", "source",
})
_LIMIT_KEYS = frozenset({"schema", "request_micro_usd", "day_micro_usd", "month_micro_usd"})


def _validate_rate_card_entry(entry, *, now_ms):
    """Mọi điều kiện của P3/L2/L3/L4. Thiếu bất kỳ thứ nào → `PRICING_UNVERIFIED`.

    Không có nhánh nào "tạm cho qua": đây là chỗ duy nhất quyết định một model có
    được tính giá hay không, và sai ở đây là mất tiền thật.
    """
    if type(entry) is not dict or frozenset(entry) != _ENTRY_KEYS:
        raise LedgerError("PRICING_UNVERIFIED", "ENTRY_SCHEMA")
    if not all(_is_str(entry[k], 1, 256) for k in ("provider", "model", "endpoint", "source")):
        raise LedgerError("PRICING_UNVERIFIED", "ENTRY_FIELDS")
    if entry["currency"] != "USD":
        # Quy đổi tiền tệ cần tỉ giá có nguồn và thời điểm — chưa có, nên chặn (L4).
        raise LedgerError("PRICING_UNVERIFIED", "CURRENCY")
    for key in ("input_micro_usd_per_mtok", "output_micro_usd_per_mtok"):
        if not _is_int(entry[key], 0, MAX_UNIT_PRICE):
            raise LedgerError("PRICING_UNVERIFIED", "UNIT_PRICE")
    if not _is_int(entry["request_fee_micro_usd"], 0, MAX_AMOUNT_MICRO_USD):
        raise LedgerError("PRICING_UNVERIFIED", "REQUEST_FEE")
    if entry["bound_method"] not in VERIFIED_BOUND_METHODS:
        raise LedgerError("PRICING_UNVERIFIED", "BOUND_METHOD")
    for key in ("bound_overhead_tokens_per_message", "bound_overhead_tokens_fixed"):
        if not _is_int(entry[key], 0, 100_000):
            raise LedgerError("PRICING_UNVERIFIED", "BOUND_OVERHEAD")
    # `is not True` để một chuỗi rỗng/None/1 không đi qua được chỗ này.
    if entry["billable_inputs_verified"] is not True:
        raise LedgerError("PRICING_UNVERIFIED", "BILLABLE_UNVERIFIED")
    if entry["output_includes_reasoning_cap"] is not True:
        # L3: model không chứng minh được phần suy luận ẩn nằm trong max_output_tokens
        # thì không bật ở v1 — nếu không, trần đầu ra không còn là trần.
        raise LedgerError("PRICING_UNVERIFIED", "REASONING_UNCAPPED")
    if not _is_int(entry["verified_at_ms"], 0, 2**53 - 1) or not _is_int(entry["expires_at_ms"], 0, 2**53 - 1):
        raise LedgerError("PRICING_UNVERIFIED", "VERIFIED_AT")
    if entry["expires_at_ms"] <= entry["verified_at_ms"]:
        raise LedgerError("PRICING_UNVERIFIED", "EXPIRY_ORDER")
    if entry["expires_at_ms"] - entry["verified_at_ms"] > RATE_CARD_MAX_AGE_MS:
        raise LedgerError("PRICING_UNVERIFIED", "EXPIRY_TOO_FAR")
    if now_ms is not None and now_ms >= entry["expires_at_ms"]:
        raise LedgerError("PRICING_UNVERIFIED", "EXPIRED")
    return entry


def pricing_revision(entry) -> str:
    """P3: `revisions.pricing` = băm của **đúng mục** rate card đang dùng.

    Sửa một con số giá, đổi endpoint, hay xác minh lại rate card đều đổi băm này →
    snapshot cũ chết `REVISION_CHANGED` → người dùng xem lại trần phí rồi mới xác nhận.
    Không phụ thuộc người sửa nhớ tăng số phiên bản.
    """
    return "pricing:" + hashlib.sha256(canonical_json(dict(entry))).hexdigest()


def _validate_limits(limits):
    if type(limits) is not dict or frozenset(limits) != _LIMIT_KEYS:
        raise _unavailable("LIMITS_SCHEMA")
    if limits["schema"] != LIMITS_SCHEMA:
        raise _unavailable("LIMITS_SCHEMA")
    for key in ("request_micro_usd", "day_micro_usd", "month_micro_usd"):
        if not _amount(limits[key]):
            raise _unavailable("LIMITS_VALUE")
    return limits


def limits_revision(limits) -> str:
    return "limits:" + hashlib.sha256(canonical_json(dict(limits))).hexdigest()


DEFAULT_LIMITS = MappingProxyType({
    # L5: mặc định 0 — mọi yêu cầu cloud ra BUDGET_EXCEEDED cho tới khi anh Khang sửa tay.
    "schema": LIMITS_SCHEMA, "request_micro_usd": 0, "day_micro_usd": 0, "month_micro_usd": 0,
})


def load_config(path) -> tuple:
    """Đọc tệp cấu hình riêng máy (giá + hạn mức). Trả `(entries, limits)`.

    Tệp nằm cạnh kho dữ liệu trên Data1000, **không** trong Git (L4). Người sửa phải
    thay nguyên tử (`os.replace`) vì hàm này đọc một lần, không khoá tệp. Không có
    tệp → hạn mức mặc định 0 và không có giá nào: đường cloud đóng, không phải lỗi.
    """
    try:
        raw = Path(path).read_bytes()
    except (OSError, ValueError):
        return (), dict(DEFAULT_LIMITS)
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise _unavailable("CONFIG_UNREADABLE") from None
    if type(data) is not dict or data.get("schema") != RATE_CARD_SCHEMA:
        raise _unavailable("CONFIG_SCHEMA")
    entries = data.get("entries")
    if type(entries) is not list or len(entries) > 256:
        raise _unavailable("CONFIG_ENTRIES")
    limits = data.get("limits")
    limits = dict(DEFAULT_LIMITS) if limits is None else _validate_limits(limits)
    # Chưa kiểm hạn dùng ở đây (now chưa biết): `_pick_entry` kiểm lại lúc giữ tiền.
    return tuple(_validate_rate_card_entry(e, now_ms=None) for e in entries), limits


# ---------- đồng hồ và kỳ (L6, L14) ----------

def _bucket(now_ms):
    """Mốc ngày và tháng theo giờ Việt Nam, trả về dạng số nguyên so sánh được.

    Độ lệch cố định UTC+7 thay vì `zoneinfo`: Windows không có sẵn cơ sở dữ liệu múi
    giờ, và Việt Nam không đổi giờ mùa hè nên không mất gì.
    """
    local = now_ms + VN_OFFSET_MS
    days = local // 86_400_000
    day_start = days * 86_400_000 - VN_OFFSET_MS
    # Tháng: đi qua civil date để không giả định tháng 30 ngày.
    year, month = _civil(days)[:2]
    month_days = _days_from_civil(year, month, 1)
    if month == 12:
        next_days = _days_from_civil(year + 1, 1, 1)
    else:
        next_days = _days_from_civil(year, month + 1, 1)
    return (day_start, day_start + 86_400_000,
            month_days * 86_400_000 - VN_OFFSET_MS, next_days * 86_400_000 - VN_OFFSET_MS)


def _civil(days):
    """Số ngày kể từ 1970-01-01 → (năm, tháng, ngày). Thuật toán Howard Hinnant."""
    days += 719_468
    era = (days if days >= 0 else days - 146_096) // 146_097
    doe = days - era * 146_097
    yoe = (doe - doe // 1460 + doe // 36_524 - doe // 146_096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (y + 1 if m <= 2 else y), m, d


def _days_from_civil(y, m, d):
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146_097 + doe - 719_468


def _check_clock(conn, now_ms):
    """Mốc cao nhất bền vững (L14, điều kiện 6).

    Ba chuyện khác nhau, chặn cả ba:
    - lùi quá 5 phút → chặn thẳng;
    - lùi **qua ranh giới ngày hoặc tháng** dù chỉ 1 ms → chặn, vì nếu không thì lùi
      đồng hồ một chút quanh nửa đêm là được cấp lại nguyên hạn mức ngày;
    - nhảy tới tương lai bất thường → chặn, vì mốc cao nhất sẽ kẹt ở đó và mọi lượt
      sau bị coi là lùi.

    Không đụng khoản đang giữ: đồng hồ lùi làm **chặn giữ thêm**, không làm mất tiền
    đã giữ.
    """
    row = conn.execute("SELECT high_water_ms FROM ledger_clock WHERE id=1").fetchone()
    high = None if row is None else row[0]
    if high is not None:
        if now_ms < high - CLOCK_BACK_TOLERANCE_MS:
            raise _unavailable("CLOCK_BACKWARD")
        if now_ms < high and _bucket(now_ms)[0] != _bucket(high)[0]:
            raise _unavailable("CLOCK_BACKWARD_DAY")
        if now_ms < high and _bucket(now_ms)[2] != _bucket(high)[2]:
            raise _unavailable("CLOCK_BACKWARD_MONTH")
        if now_ms > high + CLOCK_FORWARD_MAX_MS:
            raise _unavailable("CLOCK_FORWARD")
    conn.execute("INSERT INTO ledger_clock(id, high_water_ms) VALUES(1, ?)"
                 " ON CONFLICT(id) DO UPDATE SET high_water_ms=MAX(high_water_ms, excluded.high_water_ms)",
                 (now_ms,))


# ---------- schema ----------

def ensure_schema(conn) -> None:
    """Bảng riêng của sổ. Không đụng bảng của Service, snapshot hay grant.

    `CHECK` là lớp cuối cùng chứ không phải lớp duy nhất: mọi giá trị đã qua
    `_is_int` trước khi tới đây. Nó bắt được đúng thứ Python không bắt được — bản ghi
    do phiên bản khác hoặc sửa tay ghi vào.
    """
    conn.execute(f"""CREATE TABLE IF NOT EXISTS ledger_attempts(
        attempt_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL UNIQUE,
        grant_id TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        pricing_revision TEXT NOT NULL,
        pricing_pinned BLOB NOT NULL,
        limits_revision TEXT NOT NULL,
        reserved_micro_usd INTEGER NOT NULL
            CHECK(typeof(reserved_micro_usd)='integer' AND reserved_micro_usd > 0 AND reserved_micro_usd <= {MAX_AMOUNT_MICRO_USD}),
        actual_micro_usd INTEGER
            CHECK(actual_micro_usd IS NULL OR (typeof(actual_micro_usd)='integer'
                  AND actual_micro_usd >= 0 AND actual_micro_usd <= {MAX_AMOUNT_MICRO_USD})),
        started_at_ms INTEGER NOT NULL CHECK(typeof(started_at_ms)='integer'),
        deadline_ms INTEGER NOT NULL CHECK(typeof(deadline_ms)='integer'),
        owner_id TEXT NOT NULL,
        owner_pid INTEGER NOT NULL,
        owner_start_token TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ({_STATES_SQL})),
        ended_at_ms INTEGER,
        end_reason TEXT)""")
    conn.execute("CREATE INDEX IF NOT EXISTS ledger_attempts_state ON ledger_attempts(state, started_at_ms)")
    # Chỉ ghi thêm (L16). Không có đường xoá trong mã; không tự purge.
    conn.execute("""CREATE TABLE IF NOT EXISTS ledger_events(
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id TEXT NOT NULL,
        at_ms INTEGER NOT NULL,
        from_state TEXT,
        to_state TEXT NOT NULL,
        amount_micro_usd INTEGER,
        reason TEXT NOT NULL,
        principal_sha256 TEXT,
        evidence TEXT)""")
    conn.execute("CREATE INDEX IF NOT EXISTS ledger_events_attempt ON ledger_events(attempt_id, event_id)")
    conn.execute("""CREATE TABLE IF NOT EXISTS ledger_locks(
        provider TEXT PRIMARY KEY,
        locked_at_ms INTEGER NOT NULL,
        reason TEXT NOT NULL,
        attempt_id TEXT NOT NULL)""")
    conn.execute("CREATE TABLE IF NOT EXISTS ledger_clock(id INTEGER PRIMARY KEY CHECK(id=1), high_water_ms INTEGER NOT NULL)")


def _event(conn, attempt_id, *, at_ms, from_state, to_state, amount, reason, principal_sha=None, evidence=None):
    conn.execute("INSERT INTO ledger_events(attempt_id, at_ms, from_state, to_state, amount_micro_usd, reason,"
                 " principal_sha256, evidence) VALUES(?,?,?,?,?,?,?,?)",
                 (attempt_id, at_ms, from_state, to_state, amount, reason, principal_sha, evidence))


# ---------- bảng đóng góp ngân sách (L7, L8, điều kiện 5) ----------

# Mỗi attempt rơi vào ĐÚNG MỘT nhánh, nên không bao giờ cộng trùng reserve và actual.
#   reserved / unresolved   → khoản giữ, MỌI kỳ (không biến mất nhờ qua nửa đêm)
#   over_reserve chưa xử lý → max(actual, reserved), MỌI kỳ
#   settled / reconciled    → actual (kể cả 0), theo kỳ của started_at attempt GỐC
#   released                → 0
_CONTRIBUTION_SQL = """
    CASE
      WHEN state IN ('reserved','unresolved') THEN reserved_micro_usd
      WHEN state = 'over_reserve' THEN MAX(reserved_micro_usd, COALESCE(actual_micro_usd, 0))
      WHEN state IN ('settled','reconciled') AND started_at_ms >= ? AND started_at_ms < ?
           THEN COALESCE(actual_micro_usd, 0)
      ELSE 0
    END"""


def _guard_overflow(conn):
    """Chặn tràn INTEGER 64 bit của SUM trước khi cộng, thay vì chờ SQLite báo lỗi.

    Mỗi dòng ≤ 10^12 và số dòng ≤ 10^6, nên tổng ≤ 10^18 < 2^63. Vượt ngưỡng là sổ
    đã ở tình trạng không ai hình dung tới: chặn, không đoán (L15).
    """
    count = conn.execute("SELECT COUNT(*) FROM ledger_attempts").fetchone()[0]
    if count > MAX_ROWS:
        raise _unavailable("LEDGER_TOO_LARGE")


def _period_total(conn, start, end):
    _guard_overflow(conn)
    total = conn.execute(f"SELECT COALESCE(SUM({_CONTRIBUTION_SQL}), 0) FROM ledger_attempts", (start, end)).fetchone()[0]
    if not _is_int(total, 0, 2**62):
        raise _unavailable("TOTAL_RANGE")
    return total


def budget_state(conn, *, now_ms) -> dict:
    """Tổng đang tính vào từng kỳ. Chỉ để hiển thị và test; không chuyển trạng thái."""
    ps._check_now(now_ms)
    ensure_schema(conn)
    day_start, day_end, month_start, month_end = _bucket(now_ms)
    return {"day_micro_usd": _period_total(conn, day_start, day_end),
            "month_micro_usd": _period_total(conn, month_start, month_end)}


# ---------- danh tính tiến trình giữ tiền (L10) ----------

@dataclass(frozen=True)
class OwnerIdentity:
    """Ai đang giữ khoản tiền này. `owner_id` mới mỗi lần tiến trình khởi động.

    `start_token` là mốc khởi động của tiến trình, không phải chỉ `pid`: pid được cấp
    lại, nên "pid này còn sống" chưa chứng minh **tiến trình cũ** còn sống.
    """

    owner_id: str
    pid: int
    start_token: str


def _start_token(pid):
    """Mốc khởi động của tiến trình, đọc từ /proc. Trả "" khi không đọc được.

    Chuỗi rỗng nghĩa là **chưa biết**, và chỗ nào đọc nó cũng phải hiểu như vậy
    (Windows không có /proc). Không bao giờ suy ra "đã chết" từ chỗ không biết.
    """
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_bytes()
    except (OSError, ValueError):
        return ""
    try:
        return stat[stat.rindex(b")") + 2:].split(b" ")[19].decode("ascii")
    except (ValueError, IndexError, UnicodeDecodeError):
        return ""


def current_owner() -> OwnerIdentity:
    pid = os.getpid()
    return OwnerIdentity(owner_id=secrets.token_hex(16), pid=pid, start_token=_start_token(pid))


def _owner_dead(pid, start_token):
    """True = đã chứng minh chết, False = còn sống, None = **không biết**.

    None phải dẫn tới "chờ hết deadline", không bao giờ dẫn tới "coi như chết".
    """
    if start_token == "" or not Path("/proc").is_dir():
        return None
    if not Path(f"/proc/{int(pid)}").exists():
        return True           # pid không còn: tiến trình cũ chắc chắn đã chết
    now_token = _start_token(pid)
    if now_token == "":
        return None
    return now_token != start_token   # pid được cấp lại cho tiến trình khác


# ---------- giữ tiền ----------

@dataclass(frozen=True)
class Reservation:
    """Bằng chứng khoản tiền đã được giữ **trong cùng transaction** với claim snapshot
    và tiêu thụ grant. Adapter quyết toán vào `attempt_id` này, không tự tra DB (P1)."""

    attempt_id: str
    snapshot_id: str
    grant_id: str
    reserved_micro_usd: int
    pricing_revision: str
    limits_revision: str
    deadline_ms: int


def _after_totals(tx):
    """Khe rỗng giữa bước cộng tổng và bước ghi, để test nới ra có chủ đích.

    Test hai tiến trình sát hạn mức ngủ ở đây. Nếu giữ tiền bị tách khỏi transaction
    của `authorize_dispatch`, hai tiến trình cùng lọt và test đó đỏ.
    """


class Ledger:
    """Sổ do backend dựng lúc khởi động. Không mở DB, không gọi mạng.

    `config_path` được đọc lại ở **mỗi** lần giữ tiền, không cache: người sửa hạ hạn
    mức xuống là lượt giữ tiếp theo đã chịu mức chặt hơn (điều kiện 5). Tệp phải được
    thay nguyên tử (`os.replace`), vì đọc không khoá tệp.
    """

    __slots__ = ("_config_path", "_entries", "_limits", "owner")

    def __init__(self, *, config_path=None, entries=None, limits=None, owner=None):
        self._config_path = None if config_path is None else Path(config_path)
        self._entries = () if entries is None else tuple(
            _validate_rate_card_entry(dict(e), now_ms=None) for e in entries)
        self._limits = dict(DEFAULT_LIMITS) if limits is None else _validate_limits(dict(limits))
        self.owner = current_owner() if owner is None else owner

    def _current(self):
        if self._config_path is None:
            return self._entries, self._limits
        return load_config(self._config_path)

    def _pick_entry(self, entries, *, provider, model, endpoint, now_ms):
        found = [e for e in entries
                 if e["provider"] == provider and e["model"] == model and e["endpoint"] == endpoint]
        if len(found) != 1:
            # 0: chưa có giá đã xác minh. >1: rate card mâu thuẫn — không chọn hộ.
            raise LedgerError("PRICING_UNVERIFIED", "NO_ENTRY" if not found else "AMBIGUOUS_ENTRY")
        return _validate_rate_card_entry(found[0], now_ms=now_ms)

    def reserve_locked(self, tx, *, snapshot: SnapshotView, grant_id: str, now_ms: int) -> Reservation:
        """Giữ tiền TRONG transaction của `authorize_dispatch` (P1, điều kiện 1).

        Không mở transaction, không commit, không rollback: nó đòi vé `_Tx` đúng như
        `_claim_locked`. Mọi lỗi ở đây lan ra ngoài và kéo theo rollback claim snapshot
        lẫn tiêu thụ grant — không có đường nào để lại snapshot `dispatching` mà không
        có khoản giữ.
        """
        ps._require_tx(tx)
        conn = tx.conn
        ps._check_now(now_ms)
        if type(snapshot) is not SnapshotView:
            raise _invalid("SNAPSHOT_TYPE")
        if snapshot.state != "dispatching" or snapshot.policy_decision != "CONSENT_REQUIRED":
            # Chỉ claim cloud đã thắng CAS mới tới đây; local không đi qua sổ.
            raise _invalid("SNAPSHOT_STATE")
        if type(grant_id) is not str or not _HEX32.fullmatch(grant_id):
            raise _invalid("GRANT_ID")
        ensure_schema(conn)
        _check_clock(conn, now_ms)

        provider = snapshot.target["provider"]
        model_name = snapshot.target["model"]
        endpoint = snapshot.revisions["endpoint"]
        if not _is_str(provider, 1, 256) or not _is_str(model_name, 1, 256) or not _is_str(endpoint, 1, 256):
            raise _invalid("TARGET")
        locked = conn.execute("SELECT reason FROM ledger_locks WHERE provider=?", (provider,)).fetchone()
        if locked is not None:
            raise LedgerError("PROVIDER_LOCKED", locked[0])

        entries, limits = self._current()
        _validate_limits(limits)
        entry = self._pick_entry(entries, provider=provider, model=model_name, endpoint=endpoint, now_ms=now_ms)
        revision = pricing_revision(entry)
        if revision != snapshot.revisions["pricing"]:
            # Snapshot ghim giá nào thì giữ đúng giá đó. Lệch ở đây nghĩa là snapshot
            # lẽ ra đã phải chết REVISION_CHANGED — không tự chọn giá mới thay người dùng.
            raise LedgerError("PRICING_UNVERIFIED", "PRICING_REVISION_MISMATCH")
        if snapshot.payload_bytes is None:
            raise SnapshotError("STALE_REQUEST", "PURGED")
        payload = snapshot.payload()
        messages = payload.get("messages")
        settings = payload.get("settings")
        if type(messages) is not list or type(settings) is not dict:
            raise _invalid("PAYLOAD_SHAPE")
        output_cap = settings.get("max_output_tokens")
        if not _is_int(output_cap, 1, 2048):
            raise _invalid("OUTPUT_CAP")
        bound = input_bound_tokens(entry, payload_size=snapshot.payload_size, message_count=len(messages))
        reserved = max(price_micro_usd(entry, input_tokens=bound, output_tokens=output_cap),
                       MIN_RESERVE_MICRO_USD)   # L5: rate card thử ra 0 vẫn phải chạm hạn mức 0

        day_start, day_end, month_start, month_end = _bucket(now_ms)
        _guard_overflow(conn)
        request_total = conn.execute(
            f"SELECT COALESCE(SUM({_CONTRIBUTION_SQL}), 0) FROM ledger_attempts WHERE snapshot_id=?",
            (day_start, day_end, snapshot.snapshot_id)).fetchone()[0]
        day_total = _period_total(conn, day_start, day_end)
        month_total = _period_total(conn, month_start, month_end)
        if request_total + reserved > limits["request_micro_usd"]:
            raise LedgerError("BUDGET_EXCEEDED", "REQUEST_LIMIT")
        if day_total + reserved > limits["day_micro_usd"]:
            raise LedgerError("BUDGET_EXCEEDED", "DAY_LIMIT")
        if month_total + reserved > limits["month_micro_usd"]:
            raise LedgerError("BUDGET_EXCEEDED", "MONTH_LIMIT")

        _after_totals(tx)   # khe test; cùng transaction nên không ai chen được vào
        attempt_id = secrets.token_hex(16)
        try:
            conn.execute(
                "INSERT INTO ledger_attempts(attempt_id, snapshot_id, grant_id, provider, model, endpoint,"
                " pricing_revision, pricing_pinned, limits_revision, reserved_micro_usd, started_at_ms,"
                " deadline_ms, owner_id, owner_pid, owner_start_token, state)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'reserved')",
                (attempt_id, snapshot.snapshot_id, grant_id, provider, model_name, endpoint,
                 revision, canonical_json(dict(entry)), limits_revision(limits), reserved, now_ms,
                 now_ms + DISPATCH_DEADLINE_MS, self.owner.owner_id, self.owner.pid, self.owner.start_token))
        except sqlite3.IntegrityError:
            # snapshot_id/grant_id là UNIQUE: lần giữ thứ hai cho cùng request không tồn tại (L9).
            raise _unavailable("DUPLICATE_ATTEMPT") from None
        _event(conn, attempt_id, at_ms=now_ms, from_state=None, to_state="reserved",
               amount=reserved, reason="RESERVED")
        return Reservation(attempt_id=attempt_id, snapshot_id=snapshot.snapshot_id, grant_id=grant_id,
                           reserved_micro_usd=reserved, pricing_revision=revision,
                           limits_revision=limits_revision(limits),
                           deadline_ms=now_ms + DISPATCH_DEADLINE_MS)
