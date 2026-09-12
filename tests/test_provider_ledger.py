"""LEDGER-01 (#43): sổ ngân sách nguyên tử, Reservation và quyết toán snapshot.

Quyết định: docs/LEDGER_OPTIONS.md (P1–P3, L1–L16) và tám điều kiện bắt buộc trong
issue #43. Toàn bộ chạy trên tài liệu **giả lập**, rate card **giả lập**, đồng hồ
truyền vào: không có network call, không khoá thật, không chi phí thật.

Rate card ở đây không chứng minh giá của bất kỳ nhà cung cấp thật nào — nó chỉ chứng
minh số học và luật của sổ. Xác minh giá thật là việc của người, ngoài PR này.
"""
import json
import os
import sqlite3
from pathlib import Path

import pytest

from tro_ly_van_ban import provider_grants as pg
from tro_ly_van_ban import provider_ledger as pl
from tro_ly_van_ban import provider_snapshot as ps
from tro_ly_van_ban.provider_grants import Principal
from tro_ly_van_ban.provider_ledger import Ledger, LedgerError, OwnerIdentity, Reservation
from tro_ly_van_ban.provider_snapshot import SnapshotError, TrustedConfig
from tro_ly_van_ban.service import Service

SRC = ("UBND XÃ GIẢ LẬP\nSố: 07/UBND-VP\nGiả Lập, ngày 10/09/2026\n"
       "Đề nghị các thôn gửi báo cáo số hộ nghèo trước ngày 25/09/2026.\n"
       "Ghi chú: văn bản giả lập để thử nghiệm.\n").encode()

# 2026-09-12 10:00:00 +07 — giữa ngày, giữa tháng, để các test biên tự chọn mốc riêng.
T0 = 1757646000000
UI_SECRET = b"U" * 32
ENDPOINT = "synthetic-endpoint/0"
CATALOGUE = ({"id": "ds-synthetic", "provider": "deepseek", "model": "synthetic-ds", "enabled": True},
             {"id": "local-qwen", "provider": "ollama", "model": "qwen3:0.6b", "enabled": True})


def rate_entry(**changes):
    """Mục rate card GIẢ LẬP. 1 USD/1M token vào, 2 USD/1M ra — đúng ví dụ trong L3."""
    entry = {"provider": "deepseek", "model": "synthetic-ds", "endpoint": ENDPOINT, "currency": "USD",
             "input_micro_usd_per_mtok": 1_000_000, "output_micro_usd_per_mtok": 2_000_000,
             "request_fee_micro_usd": 0, "bound_method": "byte-level-verified",
             "bound_overhead_tokens_per_message": 32, "bound_overhead_tokens_fixed": 256,
             "billable_inputs_verified": True, "output_includes_reasoning_cap": True,
             "verified_at_ms": T0 - 86_400_000, "expires_at_ms": T0 + 5 * 86_400_000,
             "source": "https://vi-du.giaLap/gia"}
    entry.update(changes)
    return entry


def limits(request=10_000_000, day=10_000_000, month=10_000_000):
    return {"schema": pl.LIMITS_SCHEMA, "request_micro_usd": request,
            "day_micro_usd": day, "month_micro_usd": month}


def make_config(entry=None, **changes):
    """Config tin cậy; `revisions.pricing` là băm của ĐÚNG mục rate card (P3)."""
    entry = rate_entry() if entry is None else entry
    base = {"models": CATALOGUE, "cloud_enabled": True,
            "revisions": {"adapter": "synthetic-adapter/0", "endpoint": ENDPOINT,
                          "pricing": pl.pricing_revision(entry)},
            "settings": {"max_output_tokens": 2048, "temperature_milli": 0, "context_tokens": None}}
    base.update(changes)
    return TrustedConfig(**base)


def extract(doc, model_id="ds-synthetic"):
    return {"operation": "extract", "model_id": model_id,
            "sources": [{"document_id": doc, "block_ids": ["b2", "b4"], "expected_version": 0}],
            "instruction": None, "facts": []}


@pytest.fixture
def env(tmp_path):
    service = Service(tmp_path, "demo")
    doc = service.ingest("a.txt", SRC, "synthetic")
    conn = sqlite3.connect(tmp_path / "state.sqlite3", isolation_level=None)
    yield service, doc, conn
    conn.close()


def ledger(entry=None, lim=None, **kwargs):
    return Ledger(entries=(rate_entry() if entry is None else entry,),
                  limits=limits() if lim is None else lim, **kwargs)


def authorize(conn, doc, *, entry=None, lim=None, led=None, now_ms=T0, config=None):
    """Đi trọn đường thật: prepare → issue grant → authorize_dispatch (giữ tiền)."""
    entry = rate_entry() if entry is None else entry
    config = make_config(entry) if config is None else config
    sid = ps.prepare_snapshot(conn, extract(doc), config=config, now_ms=now_ms).snapshot_id
    granted = pg.issue_grant(conn, sid, principal=Principal(UI_SECRET), now_ms=now_ms + 1000)
    led = ledger(entry, lim) if led is None else led
    return pg.authorize_dispatch(conn, sid, granted.token, principal=Principal(UI_SECRET),
                                 config=config, now_ms=now_ms + 2000, ledger=led)


def dem_attempts(conn):
    """Bảng chưa tồn tại cũng là 0: rollback trong SQLite cuốn theo cả CREATE TABLE,
    nên "không có bảng" chính là bằng chứng transaction đã quay lại sạch."""
    try:
        return conn.execute("SELECT COUNT(*) FROM ledger_attempts").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def attempt_row(conn, attempt_id):
    return conn.execute("SELECT state, reserved_micro_usd, actual_micro_usd, end_reason, started_at_ms"
                        " FROM ledger_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()


# ---------- L1: số học tiền ----------

def test_gia_khop_vi_du_trong_hop_dong():
    # L2/L3: I_bound = 3488 + 2×32 + 256 = 3808; R = ceil((3808×1e6 + 2048×2e6)/1e6) = 7904
    entry = rate_entry()
    assert pl.input_bound_tokens(entry, payload_size=3488, message_count=2) == 3808
    assert pl.price_micro_usd(entry, input_tokens=3808, output_tokens=2048) == 7904


def test_lam_tron_len_khong_bao_gio_xuong():
    entry = rate_entry(input_micro_usd_per_mtok=1, output_micro_usd_per_mtok=0)
    # 1 token × 1 micro-USD/1M = 0,000001 micro-USD → làm tròn LÊN thành 1.
    assert pl.price_micro_usd(entry, input_tokens=1, output_tokens=0) == 1
    assert pl.price_micro_usd(entry, input_tokens=999_999, output_tokens=0) == 1
    assert pl.price_micro_usd(entry, input_tokens=1_000_001, output_tokens=0) == 2


def test_gia_0_van_ra_0_nhung_reserve_toi_thieu_la_1(env):
    _, doc, conn = env
    entry = rate_entry(input_micro_usd_per_mtok=0, output_micro_usd_per_mtok=0, request_fee_micro_usd=0)
    assert pl.price_micro_usd(entry, input_tokens=10**6, output_tokens=10**6) == 0
    # L5: rate card thử tính ra 0 vẫn phải chạm hạn mức 0 → giữ tối thiểu 1 micro-USD.
    auth = authorize(conn, doc, entry=entry, lim=limits(request=5, day=5, month=5))
    assert auth.reservation.reserved_micro_usd == pl.MIN_RESERVE_MICRO_USD == 1


@pytest.mark.parametrize("bad", [True, False, 1.0, "1", None, -1, 10**18])
def test_so_am_bool_float_bi_tu_choi(bad):
    entry = rate_entry()
    with pytest.raises(LedgerError) as exc:
        pl.price_micro_usd(entry, input_tokens=bad, output_tokens=0)
    assert exc.value.code == "INVALID_REQUEST"


@pytest.mark.parametrize("field", ["input_micro_usd_per_mtok", "output_micro_usd_per_mtok", "request_fee_micro_usd"])
@pytest.mark.parametrize("bad", [True, 1.0, "1", None, -1])
def test_don_gia_sai_kieu_la_pricing_unverified(field, bad):
    with pytest.raises(LedgerError) as exc:
        pl._validate_rate_card_entry(rate_entry(**{field: bad}), now_ms=T0)
    assert exc.value.code == "PRICING_UNVERIFIED"


def test_so_cuc_lon_bi_chan_truoc_khi_tran():
    entry = rate_entry(input_micro_usd_per_mtok=pl.MAX_UNIT_PRICE)
    with pytest.raises(LedgerError) as exc:
        pl.price_micro_usd(entry, input_tokens=pl.MAX_TOKENS, output_tokens=0)
    assert exc.value.reason == "AMOUNT_RANGE"


# ---------- L4/L3: rate card phải được xác minh ----------

@pytest.mark.parametrize("changes, reason", [
    ({"currency": "VND"}, "CURRENCY"),
    ({"bound_method": "chars-div-4"}, "BOUND_METHOD"),
    ({"bound_method": "byte-level"}, "BOUND_METHOD"),
    ({"billable_inputs_verified": False}, "BILLABLE_UNVERIFIED"),
    ({"billable_inputs_verified": 1}, "BILLABLE_UNVERIFIED"),
    ({"output_includes_reasoning_cap": False}, "REASONING_UNCAPPED"),
    ({"expires_at_ms": T0 - 1}, "EXPIRED"),
    ({"verified_at_ms": T0, "expires_at_ms": T0 + 30 * 86_400_000}, "EXPIRY_TOO_FAR"),
    ({"expires_at_ms": T0 - 86_400_000 - 1}, "EXPIRY_ORDER"),
])
def test_rate_card_thieu_bang_chung_bi_chan(changes, reason):
    with pytest.raises(LedgerError) as exc:
        pl._validate_rate_card_entry(rate_entry(**changes), now_ms=T0)
    assert exc.value.code == "PRICING_UNVERIFIED" and exc.value.reason == reason


def test_rate_card_thieu_khoa_hoac_thua_khoa_bi_chan():
    entry = rate_entry()
    del entry["source"]
    with pytest.raises(LedgerError):
        pl._validate_rate_card_entry(entry, now_ms=T0)
    with pytest.raises(LedgerError):
        pl._validate_rate_card_entry(rate_entry(them="gì đó"), now_ms=T0)


def test_pricing_revision_doi_khi_doi_mot_con_so():
    assert pl.pricing_revision(rate_entry()) != pl.pricing_revision(rate_entry(input_micro_usd_per_mtok=999))
    assert pl.pricing_revision(rate_entry()) == pl.pricing_revision(rate_entry())


def test_rate_card_het_han_chan_truoc_khi_giu_tien(env):
    _, doc, conn = env
    entry = rate_entry(expires_at_ms=T0 + 1000)   # hết hạn trước lúc authorize (T0+2000)
    with pytest.raises(LedgerError) as exc:
        authorize(conn, doc, entry=entry)
    assert exc.value.code == "PRICING_UNVERIFIED" and exc.value.reason == "EXPIRED"
    assert dem_attempts(conn) == 0


def test_khong_co_muc_gia_cho_model_thi_chan(env):
    _, doc, conn = env
    khac = rate_entry(model="model-khac")
    # Snapshot ghim giá của `khac`, nhưng sổ chỉ có mục cho `synthetic-ds`.
    with pytest.raises(LedgerError) as exc:
        authorize(conn, doc, config=make_config(khac), led=ledger())
    assert exc.value.code == "PRICING_UNVERIFIED"


def test_pricing_revision_lech_thi_khong_tu_chon_gia_moi(env):
    _, doc, conn = env
    config = make_config()
    config = TrustedConfig(models=config.models, cloud_enabled=True, settings=config.settings,
                           revisions={**dict(config.revisions), "pricing": "pricing:khac"})
    with pytest.raises(LedgerError) as exc:
        authorize(conn, doc, config=config)
    assert exc.value.reason == "PRICING_REVISION_MISMATCH"


# ---------- L5: hạn mức ----------

def test_han_muc_mac_dinh_0_chan_moi_thu(env):
    _, doc, conn = env
    with pytest.raises(LedgerError) as exc:
        authorize(conn, doc, led=Ledger(entries=(rate_entry(),)))   # không truyền limits → mặc định 0
    assert exc.value.code == "BUDGET_EXCEEDED"
    assert dem_attempts(conn) == 0


@pytest.mark.parametrize("lim, reason", [
    (limits(request=100), "REQUEST_LIMIT"),
    (limits(day=100), "DAY_LIMIT"),
    (limits(month=100), "MONTH_LIMIT"),
])
def test_tung_han_muc_chan_rieng(env, lim, reason):
    _, doc, conn = env
    with pytest.raises(LedgerError) as exc:
        authorize(conn, doc, lim=lim)
    assert exc.value.code == "BUDGET_EXCEEDED" and exc.value.reason == reason


def test_han_muc_bi_ha_thi_ap_muc_chat_hon_o_lan_giu_sau(env, tmp_path):
    _, doc, conn = env
    path = tmp_path / "rate_cards.json"

    def ghi(lim):   # thay nguyên tử, đúng cách người sửa phải làm (L4/L5)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"schema": pl.RATE_CARD_SCHEMA, "entries": [rate_entry()], "limits": lim}),
                       encoding="utf-8")
        os.replace(tmp, path)

    ghi(limits())
    led = Ledger(config_path=path)
    auth = authorize(conn, doc, led=led)
    assert auth.reservation.reserved_micro_usd > 0
    ghi(limits(request=1, day=1, month=1))       # anh Khang hạ trần
    doc2 = Service(Path(conn.execute("PRAGMA database_list").fetchone()[2]).parent, "demo").ingest("b.txt", SRC, "synthetic")
    with pytest.raises(LedgerError) as exc:
        authorize(conn, doc2, led=led, now_ms=T0 + 10_000)
    assert exc.value.code == "BUDGET_EXCEEDED"   # không dùng lại trần cũ đã cache


def test_khong_co_tep_cau_hinh_thi_han_muc_la_0(tmp_path):
    entries, lim = pl.load_config(tmp_path / "khong-ton-tai.json")
    assert entries == () and lim == dict(pl.DEFAULT_LIMITS)
    assert lim["day_micro_usd"] == 0


def test_tep_cau_hinh_hong_thi_chan_chu_khong_doan(tmp_path):
    path = tmp_path / "rate_cards.json"
    path.write_text("{khong phai json", encoding="utf-8")
    with pytest.raises(LedgerError) as exc:
        pl.load_config(path)
    assert exc.value.code == "LEDGER_UNAVAILABLE"


# ---------- P1: Authorization mang khoản giữ, và mọi lỗi đều rollback cả ba ----------

def test_authorization_mang_reservation_khop_dong_so(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    res = auth.reservation
    assert type(res) is Reservation
    assert res.reserved_micro_usd == 7904 or res.reserved_micro_usd > 0
    assert res.grant_id == auth.grant_id and res.snapshot_id == auth.snapshot.snapshot_id
    state, reserved, actual, _, _ = attempt_row(conn, res.attempt_id)
    assert (state, reserved, actual) == ("reserved", res.reserved_micro_usd, None)
    assert conn.execute("SELECT state FROM provider_grants WHERE grant_id=?", (auth.grant_id,)).fetchone()[0] == "consumed"
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?",
                        (auth.snapshot.snapshot_id,)).fetchone()[0] == "dispatching"


class ReserveTraNone:
    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms):
        ps._require_tx(tx)
        pl.ensure_schema(tx.conn)
        return None


class ReserveTraSaiKieu:
    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms):
        pl.ensure_schema(tx.conn)
        return {"attempt_id": "a" * 32, "reserved_micro_usd": 10}


class ReserveKhongGhiSo:
    """Trả Reservation đẹp nhưng KHÔNG ghi dòng sổ nào — ledger giả."""

    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms):
        pl.ensure_schema(tx.conn)
        return Reservation(attempt_id="b" * 32, snapshot_id=snapshot.snapshot_id, grant_id=grant_id,
                           reserved_micro_usd=10, pricing_revision=snapshot.revisions["pricing"],
                           limits_revision="limits:gia", deadline_ms=now_ms)


class ReserveGhiSoLechTien:
    """Ghi dòng sổ một số, trả về số khác."""

    def __init__(self, real):
        self.real = real

    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms):
        res = self.real.reserve_locked(tx, snapshot=snapshot, grant_id=grant_id, now_ms=now_ms)
        return Reservation(attempt_id=res.attempt_id, snapshot_id=res.snapshot_id, grant_id=res.grant_id,
                           reserved_micro_usd=res.reserved_micro_usd + 1, pricing_revision=res.pricing_revision,
                           limits_revision=res.limits_revision, deadline_ms=res.deadline_ms)


class ReserveNo:
    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms):
        pl.ensure_schema(tx.conn)
        raise RuntimeError("sổ hỏng")


@pytest.mark.parametrize("led_factory", [
    ReserveTraNone, ReserveTraSaiKieu, ReserveKhongGhiSo, ReserveNo,
    lambda: ReserveGhiSoLechTien(ledger()),
])
def test_reserve_hong_thi_rollback_ca_ba(env, led_factory):
    """Điều kiện 1: không có Authorization hợp lệ, và snapshot lẫn grant phải quay về cũ."""
    _, doc, conn = env
    config = make_config()
    sid = ps.prepare_snapshot(conn, extract(doc), config=config, now_ms=T0).snapshot_id
    granted = pg.issue_grant(conn, sid, principal=Principal(UI_SECRET), now_ms=T0 + 1000)
    with pytest.raises((SnapshotError, RuntimeError)):
        pg.authorize_dispatch(conn, sid, granted.token, principal=Principal(UI_SECRET), config=config,
                              now_ms=T0 + 2000, ledger=led_factory())
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?", (sid,)).fetchone()[0] == "prepared"
    assert conn.execute("SELECT state, attempts_used FROM provider_grants WHERE snapshot_id=?",
                        (sid,)).fetchone() == ("issued", 0)
    assert dem_attempts(conn) == 0


def test_khong_co_ledger_thi_khong_dung_gi(env):
    _, doc, conn = env
    config = make_config()
    sid = ps.prepare_snapshot(conn, extract(doc), config=config, now_ms=T0).snapshot_id
    granted = pg.issue_grant(conn, sid, principal=Principal(UI_SECRET), now_ms=T0 + 1000)
    with pytest.raises(SnapshotError) as exc:
        pg.authorize_dispatch(conn, sid, granted.token, principal=Principal(UI_SECRET), config=config,
                              now_ms=T0 + 2000, ledger=object())
    assert exc.value.code == "LEDGER_UNAVAILABLE"
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?", (sid,)).fetchone()[0] == "prepared"


def test_reserve_khong_chay_ngoai_transaction(env):
    _, doc, conn = env
    config = make_config()
    sid = ps.prepare_snapshot(conn, extract(doc), config=config, now_ms=T0).snapshot_id
    view = ps.load_snapshot(conn, sid)
    with pytest.raises(RuntimeError, match="transaction"):
        ledger().reserve_locked(object(), snapshot=view, grant_id="a" * 32, now_ms=T0)


def test_snapshot_chua_dispatching_thi_khong_giu_tien(env):
    _, doc, conn = env
    sid = ps.prepare_snapshot(conn, extract(doc), config=make_config(), now_ms=T0).snapshot_id
    view = ps.load_snapshot(conn, sid)      # còn `prepared`
    led = ledger()
    with ps._transaction(conn) as tx:
        with pytest.raises(LedgerError) as exc:
            led.reserve_locked(tx, snapshot=view, grant_id="a" * 32, now_ms=T0)
    assert exc.value.reason == "SNAPSHOT_STATE"


def test_mot_snapshot_chi_giu_tien_mot_lan(env):
    """L9: một request = một attempt. Không có đường giữ tiền lần hai."""
    _, doc, conn = env
    auth = authorize(conn, doc)
    view = ps.load_snapshot(conn, auth.snapshot.snapshot_id)
    led = ledger()
    with ps._transaction(conn) as tx:
        with pytest.raises(LedgerError) as exc:
            led.reserve_locked(tx, snapshot=view, grant_id="c" * 32, now_ms=T0 + 3000)
    assert exc.value.reason == "DUPLICATE_ATTEMPT"
    assert dem_attempts(conn) == 1
