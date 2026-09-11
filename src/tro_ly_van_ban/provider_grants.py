"""Grant dùng một lần cho snapshot cloud — GRANT-01 (#32).

Quyết định: docs/GRANT_SCHEMA_OPTIONS.md (Astra chốt 11/09/2026, S1/S2, G1–G12 và
sáu điều kiện). Grant là quyền do người dùng cấp tại UI local cho **đúng một**
snapshot `CONSENT_REQUIRED`: token ngẫu nhiên 256 bit, DB chỉ giữ hash.

`authorize_dispatch` là đường cloud **duy nhất**. Nó sở hữu transaction: kiểm grant,
kiểm lại snapshot (`_claim_locked`), giữ ngân sách, tiêu thụ grant — cùng thành
công hoặc cùng rollback. Ledger chưa có, nên hàm **bắt buộc** nhận một ledger; không
có thì trả `LEDGER_UNAVAILABLE` và không đụng gì. Tức là hôm nay chưa có đường
nào tới mạng (điều kiện 2).

Module này là nội bộ gateway: MCP không import nó, và không có tool nào cấp hay
dùng grant.
"""
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field

from . import provider_snapshot as ps
from .provider_snapshot import AlreadyClaimed, SnapshotError, SnapshotView, TrustedConfig

GRANT_TTL_MS = 5 * 60 * 1000
RETAIN_MS = 30 * 24 * 60 * 60 * 1000
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")      # secrets.token_urlsafe(32)
_HEX32 = re.compile(r"[0-9a-f]{32}")
_PRINCIPAL_DOMAIN = b"aimarx-principal/1\x00"


class RequestExists(SnapshotError):
    """Yêu cầu cho snapshot này đã có. Không phải lỗi công khai: tầng HTTP trả trạng
    thái hiện có (bấm hai lần, gọi lại sau khi đã gửi), không tạo lần gửi thứ hai."""

    def __init__(self, grant_state, snapshot_state):
        ValueError.__init__(self, f"Yêu cầu đã có: grant {grant_state}, snapshot {snapshot_state}")
        self.code = None
        self.reason = "REQUEST_EXISTS"
        self.grant_state = grant_state
        self.snapshot_state = snapshot_state


class Principal:
    """Bằng chứng nắm bí mật phiên của UI — không phải một cái tên tự khai.

    Chỉ dựng được từ bí mật (>= 32 byte) do tiến trình UI sinh lúc khởi động. DB lưu
    SHA-256 của digest chứ không lưu digest, nên tiến trình khác (MCP cùng đọc được
    file DB) không thể từ DB suy ra thứ cần để giả làm UI.

    Điều kiện 3 của Astra: đây chỉ là định danh **phiên tiến trình**. Nó không xác
    thực người đang bấm và không phân biệt các trình duyệt. Đủ để xây và test grant;
    trước khi bật cloud thật phải gắn với phiên người dùng đã xác thực.
    """

    __slots__ = ("_digest",)

    def __init__(self, session_secret: bytes):
        if type(session_secret) is not bytes or len(session_secret) < 32:
            raise ValueError("Bí mật phiên phải là bytes, tối thiểu 32 byte")
        self._digest = hashlib.sha256(_PRINCIPAL_DOMAIN + session_secret).digest()

    def _stored(self) -> str:
        return hashlib.sha256(self._digest).hexdigest()

    def __repr__(self):
        return "Principal(<ẩn>)"


@dataclass(frozen=True)
class IssuedGrant:
    grant_id: str
    token: str = field(repr=False)   # trả về đúng một lần; không log, không đưa vào trang lỗi
    expires_at_ms: int


@dataclass(frozen=True)
class Authorization:
    """Kết quả duy nhất cho phép adapter gửi `snapshot.payload_bytes`, và chỉ tồn tại
    khi ledger đã giữ ngân sách trong cùng transaction."""

    grant_id: str
    snapshot: SnapshotView


def ensure_schema(conn) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS provider_grants(
        grant_id TEXT PRIMARY KEY,
        token_sha256 TEXT NOT NULL UNIQUE,
        snapshot_id TEXT NOT NULL UNIQUE,
        snapshot_record_sha256 TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL,
        principal_sha256 TEXT NOT NULL,
        issued_at_ms INTEGER NOT NULL,
        expires_at_ms INTEGER NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('issued','consumed','revoked','expired','voided')),
        consumed_at_ms INTEGER,
        ended_at_ms INTEGER,
        end_reason TEXT,
        max_attempts INTEGER NOT NULL DEFAULT 1 CHECK(max_attempts = 1),
        attempts_used INTEGER NOT NULL DEFAULT 0 CHECK(attempts_used BETWEEN 0 AND max_attempts))""")


def _consent_required(reason):
    return SnapshotError("CONSENT_REQUIRED", reason)


def _check_principal(principal):
    if type(principal) is not Principal:
        raise ps._invalid("PRINCIPAL")


def _token_sha(token) -> str | None:
    if type(token) is not str or not _TOKEN.fullmatch(token):
        return None
    return hashlib.sha256(token.encode("ascii")).hexdigest()


_GRANT_COLUMNS = ("grant_id, snapshot_id, snapshot_record_sha256, payload_sha256, principal_sha256,"
                  " issued_at_ms, expires_at_ms, state")


def _end_grant(conn, grant_id, state, reason, now_ms):
    return conn.execute("UPDATE provider_grants SET state=?, end_reason=?, ended_at_ms=? WHERE grant_id=? AND state='issued'",
                        (state, reason, now_ms, grant_id)).rowcount


def _snapshot_state(conn, snapshot_id):
    row = conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    return None if row is None else row[0]


def issue_grant(conn, snapshot_id: str, *, principal: Principal, now_ms: int) -> IssuedGrant:
    """Cấp grant khi người dùng bấm xác nhận tại UI local (route POST có CSRF).

    Chỉ cho snapshot `CONSENT_REQUIRED` còn `prepared` và còn hạn (G9). Hạn grant =
    min(5 phút, hạn snapshot) (G8). Snapshot đã có grant — bấm hai lần, hai tab — thì
    ném `RequestExists` với trạng thái hiện có, không bao giờ lỗi SQLite thô (điều kiện 5).
    """
    ps._check_id(snapshot_id)
    ps._check_now(now_ms)
    _check_principal(principal)
    token = secrets.token_urlsafe(32)
    grant_id = secrets.token_hex(16)
    with ps._transaction(conn):
        ensure_schema(conn)
        existing = conn.execute("SELECT state FROM provider_grants WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if existing is not None:
            raise RequestExists(existing[0], _snapshot_state(conn, snapshot_id))
        row = ps._row(conn, snapshot_id)
        if row is None:
            raise ps._invalid("SNAPSHOT_NOT_FOUND")
        view = ps._view(row)
        if view.state != "prepared":
            raise AlreadyClaimed(view.state)
        if view.policy_decision != "CONSENT_REQUIRED":
            raise ps._invalid("NOT_CONSENT_SNAPSHOT")
        if now_ms >= view.expires_at_ms or now_ms < view.created_at_ms:
            raise SnapshotError("CONSENT_EXPIRED", "SNAPSHOT_EXPIRED")
        expires = min(now_ms + GRANT_TTL_MS, view.expires_at_ms)
        record_sha256 = row[4]
        conn.execute(
            "INSERT INTO provider_grants(grant_id, token_sha256, snapshot_id, snapshot_record_sha256, payload_sha256,"
            " principal_sha256, issued_at_ms, expires_at_ms, state) VALUES(?,?,?,?,?,?,?,?, 'issued')",
            (grant_id, _token_sha(token), snapshot_id, record_sha256, view.payload_sha256,
             principal._stored(), now_ms, expires))
    return IssuedGrant(grant_id=grant_id, token=token, expires_at_ms=expires)


def authorize_dispatch(conn, snapshot_id: str, token: str, *, principal: Principal, config: TrustedConfig,
                       now_ms: int, ledger) -> Authorization:
    """Đường cloud duy nhất. Một transaction do hàm này sở hữu (điều kiện 1):

    kiểm grant → `_claim_locked` (kiểm lại snapshot + CAS) → ledger giữ ngân sách →
    grant `issued → consumed`. Commit chỉ ở hai kết cục: thành công trọn vẹn, hoặc
    "chết có ghi nhận" (grant `expired`/`voided`, snapshot `invalidated`/`expired`).
    Mọi lỗi khác rollback cả khối — không bao giờ có snapshot `dispatching` mà grant
    chưa `consumed` (điều kiện 4).

    Mã lỗi (G10): mọi trường hợp **trước khi** khớp cả token, principal và snapshot
    đều là `CONSENT_REQUIRED`, để không thành máy dò token. Grant đã dùng chỉ trả
    trạng thái cũ (`RequestExists`) sau khi khớp đủ ba thứ, và không phát lại request.
    """
    reserve = getattr(ledger, "reserve_locked", None)
    if not callable(reserve):
        # Điều kiện 2: chưa có ledger thì chưa được gửi mạng. Không đụng DB.
        raise SnapshotError("LEDGER_UNAVAILABLE", "NO_LEDGER")
    ps._check_id(snapshot_id)
    ps._check_now(now_ms)
    ps._validate_config(config)
    _check_principal(principal)
    token_sha = _token_sha(token)
    outcome = None
    with ps._transaction(conn) as tx:
        ensure_schema(conn)
        row = None if token_sha is None else conn.execute(
            f"SELECT {_GRANT_COLUMNS} FROM provider_grants WHERE token_sha256=?", (token_sha,)).fetchone()
        if row is None:
            raise _consent_required("UNKNOWN_TOKEN")
        grant_id, grant_snapshot, bound_record, bound_payload, principal_sha, issued_at, expires_at, state = row
        if not hmac.compare_digest(principal_sha, principal._stored()):
            raise _consent_required("PRINCIPAL_MISMATCH")
        if grant_snapshot != snapshot_id:
            raise _consent_required("SNAPSHOT_MISMATCH")
        # Từ đây token, principal và snapshot đã khớp.
        if state == "consumed":
            raise RequestExists(state, _snapshot_state(conn, snapshot_id))
        if state != "issued":
            raise SnapshotError("CONSENT_EXPIRED", "GRANT_EXPIRED") if state == "expired" else _consent_required("GRANT_" + state.upper())
        if now_ms >= expires_at or now_ms < issued_at:
            _end_grant(conn, grant_id, "expired", "EXPIRED", now_ms)
            outcome = SnapshotError("CONSENT_EXPIRED", "GRANT_EXPIRED")
        else:
            snap = ps._row(conn, snapshot_id)
            if snap is None or snap[4] != bound_record or snap[6] != bound_payload:
                # Bản ghi snapshot bị thay: grant không còn nói về thứ người dùng đã xem.
                _end_grant(conn, grant_id, "voided", "BINDING_MISMATCH", now_ms)
                outcome = _consent_required("BINDING_MISMATCH")
        if outcome is None:
            try:
                view = ps._claim_locked(tx, snapshot_id, config=config, now_ms=now_ms, expected_decision="CONSENT_REQUIRED")
            except ps._SnapshotDied as died:
                _end_grant(conn, grant_id, "voided", died.error.reason, now_ms)
                outcome = died.error
            except AlreadyClaimed as claimed:
                if claimed.state == "dispatching":
                    # Snapshot cloud chỉ tới dispatching qua đây, cùng lúc grant consumed.
                    # Grant còn issued mà snapshot dispatching là dữ liệu hỏng: không đụng gì.
                    raise SnapshotError("STALE_REQUEST", "STATE_MISMATCH") from None
                _end_grant(conn, grant_id, "voided", "SNAPSHOT_" + claimed.state.upper(), now_ms)
                outcome = _consent_required("SNAPSHOT_" + claimed.state.upper())
        if outcome is None:
            reserve(tx, snapshot=view, grant_id=grant_id, now_ms=now_ms)  # lỗi ở đây → rollback cả khối
            moved = conn.execute("UPDATE provider_grants SET state='consumed', consumed_at_ms=?, attempts_used=1"
                                 " WHERE grant_id=? AND state='issued'", (now_ms, grant_id)).rowcount
            if moved != 1:  # CAS là lớp thứ hai, độc lập với khoá
                raise RequestExists("consumed", _snapshot_state(conn, snapshot_id))
    if outcome is not None:
        raise outcome  # khối with đã commit trạng thái chết
    return Authorization(grant_id=grant_id, snapshot=view)


def revoke(conn, grant_id: str, *, principal: Principal, now_ms: int) -> None:
    """Người dùng thu hồi grant chưa dùng; snapshot của nó bị huỷ cùng transaction.

    Grant đã tiêu thụ thì không thu hồi được (request có thể đã tính tiền):
    `RequestExists` với trạng thái hiện có.
    """
    if type(grant_id) is not str or not _HEX32.fullmatch(grant_id):
        raise _consent_required("UNKNOWN_GRANT")
    ps._check_now(now_ms)
    _check_principal(principal)
    with ps._transaction(conn):
        ensure_schema(conn)
        row = conn.execute("SELECT snapshot_id, principal_sha256, state FROM provider_grants WHERE grant_id=?",
                           (grant_id,)).fetchone()
        if row is None or not hmac.compare_digest(row[1], principal._stored()):
            raise _consent_required("UNKNOWN_GRANT")
        snapshot_id, _, state = row
        if state != "issued":
            raise RequestExists(state, _snapshot_state(conn, snapshot_id))
        _end_grant(conn, grant_id, "revoked", "REVOKED", now_ms)
        conn.execute("UPDATE provider_snapshots SET state='cancelled', end_reason='GRANT_REVOKED', ended_at_ms=?"
                     " WHERE snapshot_id=? AND state='prepared'", (now_ms, snapshot_id))


def revoke_all_unconsumed(conn, *, now_ms: int) -> int:
    """Nút "thu hồi hết" (ví dụ vừa thu hồi khoá API). Chỉ UI gọi; không đụng grant đã dùng."""
    ps._check_now(now_ms)
    with ps._transaction(conn):
        ensure_schema(conn)
        conn.execute("UPDATE provider_snapshots SET state='cancelled', end_reason='GRANT_REVOKED', ended_at_ms=?"
                     " WHERE state='prepared' AND snapshot_id IN (SELECT snapshot_id FROM provider_grants WHERE state='issued')",
                     (now_ms,))
        return conn.execute("UPDATE provider_grants SET state='revoked', end_reason='REVOKED_ALL', ended_at_ms=?"
                            " WHERE state='issued'", (now_ms,)).rowcount


def purge_grants(conn, *, now_ms: int) -> int:
    """Xoá hồ sơ grant **chưa bao giờ dẫn tới gửi** (revoked/expired/voided) sau 30 ngày.

    Grant `consumed` được giữ: request có thể đã tính tiền, kể cả khi snapshot đã
    `failed` hay `completed` mà chi phí còn chưa đối soát (điều kiện 6). Chưa có ledger
    để biết khi nào đối soát xong, nên hôm nay không xoá grant consumed nào.
    """
    ps._check_now(now_ms)
    with ps._transaction(conn):
        ensure_schema(conn)
        conn.execute("UPDATE provider_grants SET state='expired', end_reason='EXPIRED', ended_at_ms=expires_at_ms"
                     " WHERE state='issued' AND expires_at_ms <= ?", (now_ms,))
        return conn.execute("DELETE FROM provider_grants WHERE state IN ('revoked','expired','voided') AND ended_at_ms <= ?",
                            (now_ms - RETAIN_MS,)).rowcount
