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
def ms(iso):
    from datetime import datetime
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


T0 = ms("2026-09-12T10:00:00+07:00")
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
             "billable_inputs_verified": True, "output_includes_reasoning_cap": True, "context_limit_tokens": 32768,
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


# ---------- P2: quyết toán và đóng snapshot cùng một transaction ----------

def test_settle_dong_tien_va_snapshot_cung_luc(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    res = auth.reservation
    final = pl.settle(conn, res.attempt_id, usage=pl.Usage(input_tokens=1000, output_tokens=100),
                      outcome="completed", now_ms=T0 + 5000)
    assert final == "settled"
    state, reserved, actual, reason, _ = attempt_row(conn, res.attempt_id)
    assert (state, reason) == ("settled", "SETTLED")
    assert actual == pl.price_micro_usd(rate_entry(), input_tokens=1000, output_tokens=100) == 1200
    assert actual < reserved
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?",
                        (res.snapshot_id,)).fetchone()[0] == "completed"


def test_output_sai_nhung_usage_dung_thi_van_mat_tien(env):
    """Điều kiện 2: kết quả nghiệp vụ và quyết toán là hai trục."""
    _, doc, conn = env
    auth = authorize(conn, doc)
    final = pl.settle(conn, auth.reservation.attempt_id, usage=pl.Usage(input_tokens=1000, output_tokens=100),
                      outcome="failed", now_ms=T0 + 5000)
    assert final == "settled"                                    # tiền vẫn tính
    assert attempt_row(conn, auth.reservation.attempt_id)[2] == 1200
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?",
                        (auth.reservation.snapshot_id,)).fetchone()[0] == "failed"   # nghiệp vụ vẫn hỏng


def test_thieu_usage_thi_unresolved_chu_khong_phai_0(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    final = pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed", now_ms=T0 + 5000)
    assert final == "unresolved"
    state, reserved, actual, reason, _ = attempt_row(conn, auth.reservation.attempt_id)
    assert (state, actual, reason) == ("unresolved", None, "USAGE_MISSING")
    # Vẫn tính ĐỦ khoản giữ vào mọi kỳ, không coi là 0.
    assert pl.budget_state(conn, now_ms=T0 + 5000)["day_micro_usd"] == reserved


def test_settle_khong_bao_gio_duyet_van_ban(env):
    """Sổ không đụng phiên bản nghiệp vụ: duyệt văn bản là việc của người, chỗ khác."""
    service, doc, conn = env
    auth = authorize(conn, doc)
    before = conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0]
    pl.settle(conn, auth.reservation.attempt_id, usage=pl.Usage(input_tokens=1, output_tokens=1),
              outcome="completed", now_ms=T0 + 5000)
    assert conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0] == before


def test_finish_cong_khai_khong_di_vong_qua_so(env):
    """Điều kiện 2: không có đường đóng snapshot cloud mà bỏ qua khoản giữ."""
    _, doc, conn = env
    auth = authorize(conn, doc)
    sid = auth.reservation.snapshot_id
    with pytest.raises(SnapshotError) as exc:
        ps.finish(conn, sid, outcome="completed", now_ms=T0 + 5000)
    assert (exc.value.code, exc.value.reason) == ("SETTLEMENT_REQUIRED", "LEDGER_PENDING")
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?", (sid,)).fetchone()[0] == "dispatching"
    assert attempt_row(conn, auth.reservation.attempt_id)[0] == "reserved"


@pytest.mark.parametrize("den", ["unresolved", "over_reserve"])
def test_finish_cong_khai_van_bi_chan_khi_con_treo(env, den):
    _, doc, conn = env
    auth = authorize(conn, doc)
    conn.execute("UPDATE ledger_attempts SET state=? WHERE attempt_id=?", (den, auth.reservation.attempt_id))
    with pytest.raises(SnapshotError) as exc:
        ps.finish(conn, auth.reservation.snapshot_id, outcome="completed", now_ms=T0 + 5000)
    assert exc.value.code == "SETTLEMENT_REQUIRED"


def test_finish_snapshot_local_khong_doi_hanh_vi(env):
    """Snapshot local không có dòng sổ nào, nên hàng rào không được chạm vào nó."""
    _, doc, conn = env
    config = make_config(cloud_enabled=False)
    sid = ps.prepare_snapshot(conn, extract(doc, model_id="local-qwen"), config=config, now_ms=T0).snapshot_id
    ps.claim_for_dispatch(conn, sid, config=config, now_ms=T0 + 1000)
    ps.finish(conn, sid, outcome="completed", now_ms=T0 + 2000)
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?", (sid,)).fetchone()[0] == "completed"


def test_loi_giua_settle_va_finish_rollback_ca_khoi(env, monkeypatch):
    """Điều kiện 2: ledger, event, khoá provider và snapshot cùng sống hoặc cùng chết."""
    _, doc, conn = env
    auth = authorize(conn, doc)
    res = auth.reservation

    def no(tx, snapshot_id, *, outcome, now_ms):
        raise RuntimeError("chết ngay trước khi đóng snapshot")

    monkeypatch.setattr(ps, "_finish_locked", no)
    with pytest.raises(RuntimeError):
        pl.settle(conn, res.attempt_id, usage=pl.Usage(input_tokens=10**8, output_tokens=2048),
                  outcome="completed", now_ms=T0 + 5000)
    # Không còn dấu vết nào của lần quyết toán hỏng: tiền, sự kiện, khoá, snapshot.
    assert attempt_row(conn, res.attempt_id)[0] == "reserved"
    assert conn.execute("SELECT COUNT(*) FROM ledger_events WHERE attempt_id=? AND to_state!='reserved'",
                        (res.attempt_id,)).fetchone()[0] == 0
    assert pl.locked_providers(conn) == ()
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?",
                        (res.snapshot_id,)).fetchone()[0] == "dispatching"


# ---------- L11: usage vượt khoản giữ ----------

def test_usage_vuot_reserve_ghi_du_va_khoa_dung_provider(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    res = auth.reservation
    final = pl.settle(conn, res.attempt_id, usage=pl.Usage(input_tokens=10**8, output_tokens=2048),
                      outcome="completed", now_ms=T0 + 5000)
    assert final == "over_reserve"
    state, reserved, actual, reason, _ = attempt_row(conn, res.attempt_id)
    assert state == "over_reserve" and reason == "ACTUAL_OVER_RESERVE"
    assert actual == 100_004_096 > reserved          # ghi ĐỦ số thật, không clamp về reserved
    assert pl.locked_providers(conn) == ("deepseek",)
    # Tổng toàn cục tính đủ số thật, trên mọi kỳ.
    assert pl.budget_state(conn, now_ms=T0 + 5000)["day_micro_usd"] == actual
    assert pl.budget_state(conn, now_ms=T0 + 40 * 86_400_000)["month_micro_usd"] == actual


def test_provider_bi_khoa_thi_khong_giu_tien_them(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    pl.settle(conn, auth.reservation.attempt_id, usage=pl.Usage(input_tokens=10**8, output_tokens=2048),
              outcome="completed", now_ms=T0 + 5000)
    service = Service(Path(conn.execute("PRAGMA database_list").fetchone()[2]).parent, "demo")
    doc2 = service.ingest("b.txt", SRC, "synthetic")
    with pytest.raises(LedgerError) as exc:
        authorize(conn, doc2, now_ms=T0 + 10_000)
    assert exc.value.code == "PROVIDER_LOCKED"


def test_khoa_mot_provider_khong_khoa_provider_khac(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    pl.settle(conn, auth.reservation.attempt_id, usage=pl.Usage(input_tokens=10**8, output_tokens=2048),
              outcome="completed", now_ms=T0 + 5000)
    khac = rate_entry(provider="kimi", model="synthetic-kimi")
    assert "kimi" not in pl.locked_providers(conn)
    # Nhưng hạn mức chung vẫn bị khoản over_reserve ăn vào — khoá provider KHÔNG thay công thức tổng.
    assert pl.budget_state(conn, now_ms=T0 + 5000)["day_micro_usd"] == 100_004_096
    service = Service(Path(conn.execute("PRAGMA database_list").fetchone()[2]).parent, "demo")
    doc2 = service.ingest("c.txt", SRC, "synthetic")
    cat2 = ({"id": "kimi-synthetic", "provider": "kimi", "model": "synthetic-kimi", "enabled": True},) + CATALOGUE
    config = make_config(khac, models=cat2)
    sid = ps.prepare_snapshot(conn, extract(doc2, model_id="kimi-synthetic"), config=config,
                              now_ms=T0 + 10_000).snapshot_id
    granted = pg.issue_grant(conn, sid, principal=Principal(UI_SECRET), now_ms=T0 + 11_000)
    with pytest.raises(LedgerError) as exc:
        pg.authorize_dispatch(conn, sid, granted.token, principal=Principal(UI_SECRET), config=config,
                              now_ms=T0 + 12_000, ledger=ledger(khac))
    assert exc.value.code == "BUDGET_EXCEEDED"      # không phải PROVIDER_LOCKED


# ---------- L11/L12: idempotency và mâu thuẫn ----------

def test_settle_lap_lai_cung_ket_qua_khong_cong_tien_lan_hai(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    res = auth.reservation
    usage = pl.Usage(input_tokens=1000, output_tokens=100)
    assert pl.settle(conn, res.attempt_id, usage=usage, outcome="completed", now_ms=T0 + 5000) == "settled"
    truoc = pl.budget_state(conn, now_ms=T0 + 5000)
    assert pl.settle(conn, res.attempt_id, usage=usage, outcome="completed", now_ms=T0 + 6000) == "settled"
    assert pl.budget_state(conn, now_ms=T0 + 6000) == truoc
    assert attempt_row(conn, res.attempt_id)[2] == 1200


def test_settle_ket_qua_mau_thuan_khong_ghi_de_im_lang(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    res = auth.reservation
    pl.settle(conn, res.attempt_id, usage=pl.Usage(input_tokens=1000, output_tokens=100),
              outcome="completed", now_ms=T0 + 5000)
    with pytest.raises(LedgerError) as exc:
        pl.settle(conn, res.attempt_id, usage=pl.Usage(input_tokens=5000, output_tokens=100),
                  outcome="completed", now_ms=T0 + 6000)
    assert exc.value.reason == "SETTLEMENT_CONFLICT"
    assert attempt_row(conn, res.attempt_id)[2] == 1200      # số cũ không đổi
    # Nhưng lần gọi mâu thuẫn ĐƯỢC ghi lại để đối soát thấy.
    assert conn.execute("SELECT COUNT(*) FROM ledger_events WHERE attempt_id=? AND reason='CONFLICTING_SETTLEMENT'",
                        (res.attempt_id,)).fetchone()[0] == 1


# ---------- L13: giải phóng khoản giữ ----------

def test_chi_giai_phong_khi_chung_minh_chua_gui_byte_nao(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    res = auth.reservation
    pl.release_unsent(conn, res.attempt_id, proof=pl.UnsentProof(stage="tcp_connect", error_class="ConnectError",
                                                                bytes_sent=0), now_ms=T0 + 5000)
    state, _, actual, _, _ = attempt_row(conn, res.attempt_id)
    assert (state, actual) == ("released", 0)
    assert pl.budget_state(conn, now_ms=T0 + 5000)["day_micro_usd"] == 0     # released đóng góp 0


@pytest.mark.parametrize("proof", [
    True, False, "chưa gửi", None, 0,
    pl.UnsentProof(stage="read_timeout", error_class="ReadTimeout", bytes_sent=0),      # timeout không rõ
    pl.UnsentProof(stage="write_timeout", error_class="WriteTimeout", bytes_sent=0),
    pl.UnsentProof(stage="tcp_connect", error_class="ConnectError", bytes_sent=1),      # đã gửi byte
])
def test_bang_chung_khong_du_thi_khong_giai_phong(env, proof):
    _, doc, conn = env
    auth = authorize(conn, doc)
    with pytest.raises(LedgerError) as exc:
        pl.release_unsent(conn, auth.reservation.attempt_id, proof=proof, now_ms=T0 + 5000)
    assert exc.value.code == "INVALID_REQUEST"
    assert attempt_row(conn, auth.reservation.attempt_id)[0] == "reserved"   # tiền vẫn bị giữ


def test_released_khong_hoi_sinh_grant_da_tieu_thu(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    pl.release_unsent(conn, auth.reservation.attempt_id,
                      proof=pl.UnsentProof(stage="dns", error_class="DNSError", bytes_sent=0), now_ms=T0 + 5000)
    state, _, used = conn.execute("SELECT state, end_reason, attempts_used FROM provider_grants WHERE grant_id=?",
                                  (auth.grant_id,)).fetchone()
    assert (state, used) == ("consumed", 1)


# ---------- L12: đối soát tay ----------

def test_doi_soat_ghi_them_va_tinh_dung_ky_bat_dau(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    res = auth.reservation
    pl.settle(conn, res.attempt_id, usage=None, outcome="failed", now_ms=T0 + 5000)
    sau = T0 + 40 * 86_400_000        # đối soát ở tháng sau
    pl.reconcile(conn, res.attempt_id, principal=Principal(UI_SECRET), actual_micro_usd=4242,
                 evidence="hoá đơn GL-2026-09-0001", now_ms=sau)
    state, _, actual, reason, started = attempt_row(conn, res.attempt_id)
    assert (state, actual, reason) == ("reconciled", 4242, "RECONCILED")
    # Tính vào kỳ của attempt GỐC, không phải ngày đối soát (điều kiện 5).
    assert pl.budget_state(conn, now_ms=T0)["day_micro_usd"] == 4242
    assert pl.budget_state(conn, now_ms=sau)["day_micro_usd"] == 0
    assert pl.budget_state(conn, now_ms=sau)["month_micro_usd"] == 0
    su_kien = conn.execute("SELECT to_state, evidence, principal_sha256 FROM ledger_events"
                           " WHERE attempt_id=? ORDER BY event_id", (res.attempt_id,)).fetchall()
    assert [e[0] for e in su_kien] == ["reserved", "unresolved", "reconciled"]   # chỉ ghi thêm
    assert su_kien[-1][1] == "hoá đơn GL-2026-09-0001" and su_kien[-1][2] is not None


def test_doi_soat_0_van_dung_ky_va_khong_dem_hai_lan(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed", now_ms=T0 + 5000)
    pl.reconcile(conn, auth.reservation.attempt_id, principal=Principal(UI_SECRET), actual_micro_usd=0,
                 evidence="nhà cung cấp xác nhận không tính phí", now_ms=T0 + 10_000)
    assert attempt_row(conn, auth.reservation.attempt_id)[2] == 0
    assert pl.budget_state(conn, now_ms=T0)["day_micro_usd"] == 0
    assert pl.budget_state(conn, now_ms=T0)["month_micro_usd"] == 0


@pytest.mark.parametrize("bad", [None, "ai đó", object(), b"x" * 32])
def test_doi_soat_doi_principal_that(env, bad):
    _, doc, conn = env
    auth = authorize(conn, doc)
    pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed", now_ms=T0 + 5000)
    with pytest.raises(LedgerError) as exc:
        pl.reconcile(conn, auth.reservation.attempt_id, principal=bad, actual_micro_usd=1,
                     evidence="x", now_ms=T0 + 6000)
    assert exc.value.reason == "PRINCIPAL"


def test_doi_soat_khong_mo_khoa_khi_con_su_co_khac(env, tmp_path):
    """Điều kiện 7: chỉ mở khoá provider khi MỌI sự cố liên quan đã đối soát."""
    service, doc, conn = env
    a = authorize(conn, doc)
    doc2 = service.ingest("b.txt", SRC, "synthetic")
    b = authorize(conn, doc2, now_ms=T0 + 20_000)
    for auth in (a, b):
        pl.settle(conn, auth.reservation.attempt_id, usage=pl.Usage(input_tokens=10**8, output_tokens=2048),
                  outcome="completed", now_ms=T0 + 30_000)
    assert pl.locked_providers(conn) == ("deepseek",)
    pl.reconcile(conn, a.reservation.attempt_id, principal=Principal(UI_SECRET), actual_micro_usd=5,
                 evidence="hoá đơn 1", now_ms=T0 + 40_000)
    assert pl.locked_providers(conn) == ("deepseek",)      # còn b chưa đối soát
    pl.reconcile(conn, b.reservation.attempt_id, principal=Principal(UI_SECRET), actual_micro_usd=5,
                 evidence="hoá đơn 2", now_ms=T0 + 50_000)
    assert pl.locked_providers(conn) == ()


@pytest.mark.parametrize("evidence", ["", "x" * 501, None, 123, b"x"])
def test_bang_chung_doi_soat_phai_la_ghi_chu_ngan(env, evidence):
    _, doc, conn = env
    auth = authorize(conn, doc)
    pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed", now_ms=T0 + 5000)
    with pytest.raises(LedgerError) as exc:
        pl.reconcile(conn, auth.reservation.attempt_id, principal=Principal(UI_SECRET), actual_micro_usd=1,
                     evidence=evidence, now_ms=T0 + 6000)
    assert exc.value.reason == "EVIDENCE"


# ---------- L6/L7/L14: kỳ và đồng hồ ----------

def test_khoan_giu_khong_bien_mat_khi_qua_nua_dem(env):
    """Điều kiện 5: reserved/unresolved đóng góp đủ trên MỌI kỳ."""
    _, doc, conn = env
    truoc = ms("2026-09-12T23:00:00+07:00")                       # 2026-09-12 23:00 +07
    auth = authorize(conn, doc, now_ms=truoc)
    reserved = auth.reservation.reserved_micro_usd
    sau = ms("2026-09-13T00:20:00+07:00")                         # 2026-09-13 00:20 +07 — đã sang ngày mới
    assert pl._bucket(truoc)[0] != pl._bucket(sau)[0]
    assert pl.budget_state(conn, now_ms=sau)["day_micro_usd"] == reserved
    assert pl.budget_state(conn, now_ms=sau + 30 * 86_400_000)["month_micro_usd"] == reserved


def test_bien_nua_dem_gio_viet_nam():
    cuoi = ms("2026-09-13T00:00:00+07:00") - 1      # 2026-09-12 23:59:59,999 +07
    dau = cuoi + 1            # 2026-09-13 00:00:00,000 +07
    assert pl._bucket(cuoi)[0] != pl._bucket(dau)[0]
    assert pl._bucket(dau)[0] == dau
    # Cùng thời điểm đó theo UTC vẫn là 12/09 — nếu tính theo UTC thì hai mốc này cùng ngày.
    assert (cuoi + pl.VN_OFFSET_MS) // 86_400_000 != (dau + pl.VN_OFFSET_MS) // 86_400_000


def test_bien_thang():
    cuoi = ms("2026-10-01T00:00:00+07:00") - 1      # 2026-09-30 23:59:59,999 +07
    dau = cuoi + 1
    assert pl._bucket(cuoi)[2] != pl._bucket(dau)[2]
    assert pl._bucket(dau)[2] == dau


def test_settled_tinh_vao_ky_bat_dau_khong_phai_ngay_quyet_toan(env):
    """Điều kiện 5: settled đóng góp theo `started_at` của attempt gốc."""
    _, doc, conn = env
    truoc = ms("2026-09-12T23:00:00+07:00")                       # 12/09 23:00 +07
    auth = authorize(conn, doc, now_ms=truoc)
    sau = ms("2026-09-13T00:20:00+07:00")                         # 13/09 00:20 +07
    pl.settle(conn, auth.reservation.attempt_id, usage=pl.Usage(input_tokens=1000, output_tokens=100),
              outcome="completed", now_ms=sau)
    assert pl.budget_state(conn, now_ms=truoc + 2000)["day_micro_usd"] == 1200   # ngày 12/09
    assert pl.budget_state(conn, now_ms=sau)["day_micro_usd"] == 0               # ngày 13/09 sạch


def test_dong_ho_lui_qua_ranh_gioi_ngay_bi_chan_du_duoi_5_phut(env):
    """Điều kiện 6: lùi qua ranh giới ngày/tháng bị chặn kể cả khi dưới 5 phút."""
    _, doc, conn = env
    sau_nua_dem = ms("2026-09-13T00:00:01+07:00")   # 13/09 00:00:01 +07
    auth = authorize(conn, doc, now_ms=sau_nua_dem)
    truoc_nua_dem = ms("2026-09-13T00:00:00+07:00") - 1               # 12/09 23:59:59,999 +07 — lùi 3,001 giây
    with pytest.raises(LedgerError) as exc:
        pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed", now_ms=truoc_nua_dem)
    assert exc.value.code == "LEDGER_UNAVAILABLE" and "CLOCK_BACKWARD" in exc.value.reason


def test_dong_ho_lui_nho_trong_cung_ngay_van_chay(env):
    _, doc, conn = env
    auth = authorize(conn, doc, now_ms=T0)
    # Lùi 1 giây, cùng ngày: không phải tấn công kỳ ngân sách, không chặn.
    pl.settle(conn, auth.reservation.attempt_id, usage=pl.Usage(input_tokens=1, output_tokens=1),
              outcome="completed", now_ms=T0 + 2000 - 1000)
    assert attempt_row(conn, auth.reservation.attempt_id)[0] == "settled"


def test_dong_ho_lui_qua_5_phut_bi_chan(env):
    _, doc, conn = env
    auth = authorize(conn, doc, now_ms=T0)
    with pytest.raises(LedgerError) as exc:
        pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed",
                  now_ms=T0 + 2000 - pl.CLOCK_BACK_TOLERANCE_MS - 1)
    assert exc.value.reason == "CLOCK_BACKWARD"


def test_dong_ho_lui_khong_lam_mat_tien_dang_giu(env):
    """Điều kiện 6: đồng hồ lùi làm CHẶN giữ thêm, không làm biến mất khoản đã giữ."""
    _, doc, conn = env
    auth = authorize(conn, doc, now_ms=T0)
    reserved = auth.reservation.reserved_micro_usd
    with pytest.raises(LedgerError):
        pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed", now_ms=T0 - 10 * 86_400_000)
    assert attempt_row(conn, auth.reservation.attempt_id)[0] == "reserved"
    assert pl.budget_state(conn, now_ms=T0 + 2000)["day_micro_usd"] == reserved


def test_thoi_gian_tuong_lai_hoang_khong_lam_hong_so(env):
    _, doc, conn = env
    auth = authorize(conn, doc, now_ms=T0)
    xa = T0 + 100 * 365 * 86_400_000            # năm 2126
    with pytest.raises(LedgerError) as exc:
        pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed", now_ms=xa)
    assert exc.value.reason == "CLOCK_FORWARD"
    # Mốc cao nhất KHÔNG bị nhiễm: sổ chạy tiếp bình thường với giờ đúng.
    assert conn.execute("SELECT high_water_ms FROM ledger_clock").fetchone()[0] < xa
    pl.settle(conn, auth.reservation.attempt_id, usage=None, outcome="failed", now_ms=T0 + 5000)
    assert attempt_row(conn, auth.reservation.attempt_id)[0] == "unresolved"


def test_nhieu_provider_va_khoan_ky_cu_khong_tao_han_muc_gia(env):
    """Điều kiện 5: khoản treo của kỳ CŨ vẫn ăn hạn mức của kỳ MỚI, ở mọi provider."""
    service, doc, conn = env
    cu = authorize(conn, doc, now_ms=T0)
    pl.settle(conn, cu.reservation.attempt_id, usage=None, outcome="failed", now_ms=T0 + 5000)  # unresolved
    treo = cu.reservation.reserved_micro_usd
    sang_thang = ms("2026-10-01T01:00:00+07:00")      # 01/10/2026 01:00 +07
    doc2 = service.ingest("b.txt", SRC, "synthetic")
    with pytest.raises(LedgerError) as exc:
        authorize(conn, doc2, entry=rate_entry(verified_at_ms=sang_thang - 1000, expires_at_ms=sang_thang + 86_400_000),
                  lim=limits(request=10_000_000, day=treo + 10, month=treo + 10), now_ms=sang_thang)
    assert exc.value.code == "BUDGET_EXCEEDED"   # sang tháng mới vẫn không được cấp lại hạn mức


# ---------- L10: khởi động lại và recovery ----------

def _owner(pid, token):
    return OwnerIdentity(owner_id="a" * 32, pid=pid, start_token=token)


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="Linux process identity probe")
def test_owner_da_chet_thi_chuyen_unresolved_ngay(env):
    _, doc, conn = env
    chet = _owner(999_999_999, "12345")          # pid không tồn tại → chứng minh được là chết
    auth = authorize(conn, doc, led=ledger(owner=chet))
    assert pl._owner_dead(999_999_999, "12345") is True
    assert pl.recover_on_start(conn, now_ms=T0 + 3000) == 1      # ngay, không chờ deadline
    state, reserved, actual, reason, _ = attempt_row(conn, auth.reservation.attempt_id)
    assert (state, actual, reason) == ("unresolved", None, "OWNER_DEAD")
    assert pl.budget_state(conn, now_ms=T0 + 3000)["day_micro_usd"] == reserved   # vẫn tính đủ phí


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="Linux process identity probe")
def test_owner_con_song_thi_khong_dung_toi_du_mo_them_connection(env, tmp_path):
    """Điều kiện 6: không đổi reserved của tiến trình còn sống chỉ vì mở thêm connection."""
    _, doc, conn = env
    song = _owner(os.getpid(), pl._start_token(os.getpid()))
    auth = authorize(conn, doc, led=ledger(owner=song))
    assert pl._owner_dead(song.pid, song.start_token) is False
    khac = sqlite3.connect(tmp_path / "state.sqlite3", isolation_level=None)
    try:
        assert pl.recover_on_start(khac, now_ms=T0 + 3000) == 0
    finally:
        khac.close()
    assert attempt_row(conn, auth.reservation.attempt_id)[0] == "reserved"


def test_chua_chung_minh_duoc_chet_thi_cho_het_deadline(env):
    """start_token rỗng = KHÔNG BIẾT (ví dụ Windows). Không bao giờ suy ra 'đã chết'."""
    _, doc, conn = env
    chua_biet = _owner(1, "")
    auth = authorize(conn, doc, led=ledger(owner=chua_biet))
    assert pl._owner_dead(1, "") is None
    deadline = auth.reservation.deadline_ms
    assert pl.recover_on_start(conn, now_ms=deadline) == 0                       # chưa tới hạn bền vững
    assert pl.recover_on_start(conn, now_ms=deadline + pl.RECOVERY_GRACE_MS - 1) == 0
    assert pl.recover_on_start(conn, now_ms=deadline + pl.RECOVERY_GRACE_MS) == 1
    assert attempt_row(conn, auth.reservation.attempt_id)[3] == "DEADLINE_PASSED"


def test_recovery_chay_lai_nhieu_lan_van_cung_ket_qua(env):
    _, doc, conn = env
    auth = authorize(conn, doc, led=ledger(owner=_owner(999_999_999, "1")))
    sau = auth.reservation.deadline_ms + pl.RECOVERY_GRACE_MS + 1
    assert pl.recover_on_start(conn, now_ms=sau) == 1
    assert pl.recover_on_start(conn, now_ms=sau + 1000) == 0
    assert pl.recover_on_start(conn, now_ms=sau + 2000) == 0
    su_kien = conn.execute("SELECT COUNT(*) FROM ledger_events WHERE attempt_id=? AND to_state='unresolved'",
                           (auth.reservation.attempt_id,)).fetchone()[0]
    assert su_kien == 1                                   # không ghi thêm dòng mỗi lần chạy lại


def test_recovery_khong_phat_lai_request_va_khong_hoi_sinh_grant(env, monkeypatch):
    monkeypatch.setattr(pl, "_owner_dead", lambda *_: True)
    _, doc, conn = env
    auth = authorize(conn, doc, led=ledger(owner=_owner(999_999_999, "1")))
    pl.recover_on_start(conn, now_ms=T0 + 3000)
    assert conn.execute("SELECT state, attempts_used FROM provider_grants WHERE grant_id=?",
                        (auth.grant_id,)).fetchone() == ("consumed", 1)
    # Snapshot bị đóng failed cùng transaction, không phát lại gì.
    assert conn.execute("SELECT state FROM provider_snapshots WHERE snapshot_id=?",
                        (auth.reservation.snapshot_id,)).fetchone()[0] == "failed"


def test_recovery_bo_qua_khoan_cua_chinh_minh(env):
    _, doc, conn = env
    toi = _owner(999_999_999, "1")               # cố tình "chết" để chứng minh nhánh owner_id thắng
    authorize(conn, doc, led=ledger(owner=toi))
    assert pl.recover_on_start(conn, now_ms=T0 + 10**7, owner=toi) == 0


# ---------- hai TIẾN TRÌNH sát hạn mức ----------

def _cham_lai(tx):
    import time
    time.sleep(0.05)


def _reserve_worker(db_path, sid, token, entry, lim, barrier, out):
    """Chạy trong tiến trình riêng. Nới khe ĐÚNG giữa bước cộng tổng và bước ghi."""
    import tro_ly_van_ban.provider_ledger as child_pl
    child_pl._after_totals = _cham_lai
    conn = sqlite3.connect(db_path, isolation_level=None)
    config = make_config(entry)
    try:
        barrier.wait(60)
        led = Ledger(entries=(entry,), limits=lim)
        auth = pg.authorize_dispatch(conn, sid, token, principal=Principal(UI_SECRET), config=config,
                                     now_ms=T0 + 2000, ledger=led)
        out.put(("won", auth.reservation.reserved_micro_usd))
    except Exception as err:   # noqa: BLE001 — cần thấy cả OperationalError
        out.put(("error", type(err).__name__ + ":" + str(getattr(err, "reason", ""))))
    finally:
        conn.close()


@pytest.mark.parametrize("goc", ["local", "data1000"])
def test_hai_tien_trinh_sat_han_muc_tong_khong_vuot(tmp_path, goc, request):
    """Nghiệm thu bắt buộc: hai TIẾN TRÌNH giữ tiền sát hạn mức, tổng không vượt.

    Khe được nới có chủ đích trong `_after_totals`, đúng giữa lúc cộng tổng và lúc ghi.
    Nếu giữ tiền bị tách khỏi transaction của `authorize_dispatch`, cả hai cùng lọt.
    """
    if goc == "data1000":
        if os.getenv("AIMARX_TEST_DATA1000") != "1":
            pytest.skip("Opt-in Data1000 test: set AIMARX_TEST_DATA1000=1")
        root = Path("/run/media/asus/Data1000/AIMarx/workspace/_ledger_test")
        if not Path("/run/media/asus/Data1000").is_mount():
            pytest.skip("Data1000 không gắn — ghi CHƯA KIỂM, không thay bằng thư mục cùng tên ổ khác")
        # Xác minh đúng ổ: thiết bị của Data1000 phải khác thiết bị của /home.
        if os.stat("/run/media/asus/Data1000").st_dev == os.stat(str(Path.home())).st_dev:
            pytest.skip("Đường dẫn Data1000 nằm cùng thiết bị với /home — không phải ổ thật")
        root.mkdir(parents=True, exist_ok=True)
        base = Path(__import__("tempfile").mkdtemp(dir=root))
        request.addfinalizer(lambda: __import__("shutil").rmtree(base, ignore_errors=True))
    else:
        base = tmp_path

    service = Service(base, "demo")
    doc = service.ingest("a.txt", SRC, "synthetic")
    conn = sqlite3.connect(base / "state.sqlite3", isolation_level=None)
    entry = rate_entry()
    config = make_config(entry)
    jobs = []
    for _ in range(2):
        sid = ps.prepare_snapshot(conn, extract(doc), config=config, now_ms=T0).snapshot_id
        jobs.append((sid, pg.issue_grant(conn, sid, principal=Principal(UI_SECRET), now_ms=T0 + 1000).token))
    # Hạn mức vừa đủ MỘT khoản giữ: ai thắng cũng được, hai người cùng thắng thì hỏng.
    mot = 7904
    lim = limits(request=mot, day=mot, month=mot)

    ctx = __import__("multiprocessing").get_context("spawn")
    barrier, out = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_reserve_worker,
                           args=(str(base / "state.sqlite3"), sid, token, entry, lim, barrier, out))
               for sid, token in jobs]
    for w in workers:
        w.start()
    ket_qua = [out.get(timeout=180) for _ in workers]
    for w in workers:
        w.join(60)

    thang = [r for r in ket_qua if r[0] == "won"]
    assert len(thang) == 1, ket_qua                      # đúng một tiến trình giữ được tiền
    tong = conn.execute("SELECT COALESCE(SUM(reserved_micro_usd), 0) FROM ledger_attempts"
                        " WHERE state='reserved'").fetchone()[0]
    assert tong <= mot, (tong, ket_qua)                  # tổng KHÔNG vượt hạn mức
    assert conn.execute("SELECT COUNT(*) FROM ledger_attempts").fetchone()[0] == 1
    conn.close()

# ---------- Astra completion: lifecycle, replay and adversarial boundaries ----------

@pytest.mark.parametrize('changed', ['outcome', 'usage_same_price'])
def test_settlement_replay_checks_full_result(env, changed):
    _, doc, conn = env
    res = authorize(conn, doc).reservation
    pl.settle(conn, res.attempt_id, usage=pl.Usage(1000, 100), outcome='completed', now_ms=T0+5000)
    usage = pl.Usage(1000, 100) if changed == 'outcome' else pl.Usage(800, 200)
    outcome = 'failed' if changed == 'outcome' else 'completed'
    with pytest.raises(LedgerError, match='LEDGER_UNAVAILABLE'):
        pl.settle(conn, res.attempt_id, usage=usage, outcome=outcome, now_ms=T0+6000)
    assert attempt_row(conn, res.attempt_id)[2] == 1200
    assert ps.load_snapshot(conn, res.snapshot_id).state == 'completed'


def test_reconcile_exact_replay_and_conflict(env):
    _, doc, conn = env
    res = authorize(conn, doc).reservation
    pl.mark_unresolved(conn, res.attempt_id, reason='TRANSPORT_TIMEOUT', now_ms=T0+5000)
    args = dict(principal=Principal(UI_SECRET), actual_micro_usd=17, evidence='invoice-17', now_ms=T0+6000)
    pl.reconcile(conn, res.attempt_id, **args)
    count = conn.execute('SELECT COUNT(*) FROM ledger_events').fetchone()[0]
    pl.reconcile(conn, res.attempt_id, **{**args, 'now_ms': T0+7000})
    assert conn.execute('SELECT COUNT(*) FROM ledger_events').fetchone()[0] == count
    for changes in ({'actual_micro_usd': 18}, {'evidence': 'other'}, {'principal': Principal(b'V'*32)}):
        with pytest.raises(LedgerError):
            pl.reconcile(conn, res.attempt_id, **{**args, **changes})
    assert attempt_row(conn, res.attempt_id)[2] == 17
    assert ps.load_snapshot(conn, res.snapshot_id).state == 'failed'


@pytest.mark.parametrize('operation', ['release', 'unresolved', 'recover', 'reconcile'])
def test_failure_paths_close_snapshot_atomically(env, monkeypatch, operation):
    _, doc, conn = env
    res = authorize(conn, doc).reservation
    if operation == 'reconcile':
        # Simulate a durable unresolved row from an interrupted older backend.
        conn.execute("UPDATE ledger_attempts SET state='unresolved' WHERE attempt_id=?", (res.attempt_id,))
    before = list(conn.iterdump())
    monkeypatch.setattr(pl, '_owner_dead', lambda *_: True)
    def fail(*args, **kwargs):
        raise RuntimeError('fault injection')
    with monkeypatch.context() as patch:
        patch.setattr(ps, '_finish_locked', fail)
        with pytest.raises(RuntimeError):
            if operation == 'release':
                pl.release_unsent(conn, res.attempt_id, proof=pl.UnsentProof('dns', 'DNSError', 0), now_ms=T0+5000)
            elif operation == 'unresolved':
                pl.mark_unresolved(conn, res.attempt_id, reason='TRANSPORT_TIMEOUT', now_ms=T0+5000)
            elif operation == 'recover':
                pl.recover_on_start(conn, now_ms=T0+5000)
            else:
                pl.reconcile(conn, res.attempt_id, principal=Principal(UI_SECRET), actual_micro_usd=0,
                             evidence='invoice', now_ms=T0+5000)
    assert list(conn.iterdump()) == before


def test_release_replay_closes_snapshot_and_does_not_store_error_text(env):
    _, doc, conn = env
    res = authorize(conn, doc).reservation
    sentinel = 'TOKEN_KEY_PAYLOAD_SENTINEL'
    proof = pl.UnsentProof('dns', sentinel, 0)
    pl.release_unsent(conn, res.attempt_id, proof=proof, now_ms=T0+5000)
    before = list(conn.iterdump())
    pl.release_unsent(conn, res.attempt_id, proof=proof, now_ms=T0+5000)
    assert list(conn.iterdump()) == before
    assert sentinel not in '\n'.join(before)
    assert ps.load_snapshot(conn, res.snapshot_id).state == 'failed'
    with pytest.raises(LedgerError):
        pl.release_unsent(conn, res.attempt_id, proof=pl.UnsentProof('tcp_connect', 'Error', 0), now_ms=T0+5000)


@pytest.mark.parametrize('bad', [True, 1.0, -1, 10**30])
def test_invalid_usage_rejected_even_on_replay(env, bad):
    _, doc, conn = env
    res = authorize(conn, doc).reservation
    pl.settle(conn, res.attempt_id, usage=pl.Usage(1, 1), outcome='failed', now_ms=T0+5000)
    with pytest.raises(LedgerError):
        pl.settle(conn, res.attempt_id, usage=pl.Usage(bad, 1), outcome='failed', now_ms=T0+5000)


def test_pinned_price_settlement_survives_current_config_missing(env, tmp_path):
    _, doc, conn = env
    path = tmp_path/'prices.json'
    path.write_text(json.dumps({'schema':pl.RATE_CARD_SCHEMA, 'entries':[rate_entry()], 'limits':limits()}))
    led = Ledger(config_path=path)
    res = authorize(conn, doc, led=led).reservation
    path.unlink()
    pl.settle(conn, res.attempt_id, usage=pl.Usage(1000, 100), outcome='failed', now_ms=T0+40*86_400_000)
    assert attempt_row(conn, res.attempt_id)[2] == 1200


@pytest.mark.parametrize('field,value', [('provider','kimi'), ('model','other'), ('endpoint','other'),
                                        ('pricing_revision','other'), ('limits_revision','other'), ('deadline_ms',0)])
def test_reservation_must_match_all_persisted_bindings(env, field, value):
    _, doc, conn = env
    class Tampered(Ledger):
        def reserve_locked(self, tx, **kwargs):
            res = super().reserve_locked(tx, **kwargs)
            tx.conn.execute(f'UPDATE ledger_attempts SET {field}=? WHERE attempt_id=?', (value, res.attempt_id))
            return res
    with pytest.raises(SnapshotError):
        authorize(conn, doc, led=Tampered(entries=(rate_entry(),), limits=limits()))
    assert dem_attempts(conn) == 0
    assert conn.execute('SELECT state FROM provider_snapshots').fetchone()[0] == 'prepared'
    assert conn.execute('SELECT state FROM provider_grants').fetchone()[0] == 'issued'


def test_mutable_reservation_impostor_rejected(env):
    from types import SimpleNamespace
    _, doc, conn = env
    class Impostor(Ledger):
        def reserve_locked(self, tx, **kwargs):
            res = super().reserve_locked(tx, **kwargs)
            return SimpleNamespace(**vars(res))
    with pytest.raises(SnapshotError):
        authorize(conn, doc, led=Impostor(entries=(rate_entry(),), limits=limits()))
    assert dem_attempts(conn) == 0


@pytest.mark.parametrize('point', ['2026-09-13T00:00:00+07:00', '2026-10-01T00:00:00+07:00'])
def test_clock_backward_one_millisecond_across_bucket(env, point):
    _, doc, conn = env
    midnight = ms(point)
    entry = rate_entry(verified_at_ms=midnight-86_400_000, expires_at_ms=midnight+86_400_000)
    res = authorize(conn, doc, entry=entry, now_ms=midnight-2000).reservation
    assert conn.execute('SELECT high_water_ms FROM ledger_clock').fetchone()[0] == midnight
    with pytest.raises(LedgerError):
        pl.settle(conn, res.attempt_id, usage=None, outcome='failed', now_ms=midnight-1)
    assert attempt_row(conn, res.attempt_id)[0] == 'reserved'


def test_future_verification_is_not_verified(env):
    _, doc, conn = env
    with pytest.raises(LedgerError) as err:
        authorize(conn, doc, entry=rate_entry(verified_at_ms=T0+5000))
    assert err.value.reason == 'VERIFIED_IN_FUTURE'


def test_unknown_unresolved_reason_never_logged(env):
    _, doc, conn = env
    res = authorize(conn, doc).reservation
    sentinel = 'TOKEN_KEY_PAYLOAD_SENTINEL'
    with pytest.raises(LedgerError) as err:
        pl.mark_unresolved(conn, res.attempt_id, reason=sentinel, now_ms=T0+5000)
    assert sentinel not in str(err.value)
    assert sentinel not in '\n'.join(conn.iterdump())


def test_sqlite_error_is_sanitized_and_all_state_rolled_back(env):
    _, doc, conn = env
    res = authorize(conn, doc).reservation
    conn.execute("CREATE TRIGGER fail_event BEFORE INSERT ON ledger_events BEGIN SELECT RAISE(ABORT, 'SECRET_SENTINEL'); END")
    with pytest.raises(SnapshotError) as err:
        pl.settle(conn, res.attempt_id, usage=pl.Usage(1,1), outcome='completed', now_ms=T0+5000)
    assert err.value.code == 'LEDGER_UNAVAILABLE'
    assert 'SECRET_SENTINEL' not in str(err.value)
    assert attempt_row(conn, res.attempt_id)[0] == 'reserved'
    assert ps.load_snapshot(conn, res.snapshot_id).state == 'dispatching'
    assert not conn.in_transaction


def test_readonly_ledger_never_authorizes(env, tmp_path):
    _, doc, conn = env
    config = make_config()
    sid = ps.prepare_snapshot(conn, extract(doc), config=config, now_ms=T0).snapshot_id
    grant = pg.issue_grant(conn, sid, principal=Principal(UI_SECRET), now_ms=T0+1000)
    path = (tmp_path/'state.sqlite3').resolve().as_uri() + '?mode=ro'
    ro = sqlite3.connect(path, uri=True, isolation_level=None)
    try:
        with pytest.raises(SnapshotError) as err:
            pg.authorize_dispatch(ro, sid, grant.token, principal=Principal(UI_SECRET), config=config,
                                  now_ms=T0+2000, ledger=ledger())
        assert err.value.code == 'LEDGER_UNAVAILABLE'
    finally:
        ro.close()
    assert pg._snapshot_state(conn, sid) == 'prepared'
    assert conn.execute('SELECT state FROM provider_grants').fetchone()[0] == 'issued'


def _crash_lifecycle(db_path, operation, sid, token, attempt_id):
    conn = sqlite3.connect(db_path, isolation_level=None)
    if operation == 'reserve':
        class CrashAfterReserve(Ledger):
            def reserve_locked(self, tx, **kwargs):
                super().reserve_locked(tx, **kwargs)
                os._exit(17)
        pg.authorize_dispatch(conn, sid, token, principal=Principal(UI_SECRET), config=make_config(),
                              now_ms=T0+2000, ledger=CrashAfterReserve(entries=(rate_entry(),), limits=limits()))
    else:
        original = ps._finish_locked
        def crash(tx, sid, **kwargs):
            if operation == 'after_finish':
                original(tx, sid, **kwargs)
            os._exit(17)
        ps._finish_locked = crash
        pl.settle(conn, attempt_id, usage=pl.Usage(10**8,2048), outcome='completed', now_ms=T0+5000)


@pytest.mark.parametrize('operation', ['reserve', 'before_finish', 'after_finish'])
def test_real_process_crash_rolls_back_whole_lifecycle(env, tmp_path, operation):
    import multiprocessing
    _, doc, conn = env
    config = make_config()
    sid = ps.prepare_snapshot(conn, extract(doc), config=config, now_ms=T0).snapshot_id
    grant = pg.issue_grant(conn, sid, principal=Principal(UI_SECRET), now_ms=T0+1000)
    attempt_id = None
    if operation != 'reserve':
        auth = pg.authorize_dispatch(conn, sid, grant.token, principal=Principal(UI_SECRET), config=config,
                                     now_ms=T0+2000, ledger=ledger())
        attempt_id = auth.reservation.attempt_id
    before = list(conn.iterdump())
    worker = multiprocessing.get_context('spawn').Process(target=_crash_lifecycle,
                    args=(str(tmp_path/'state.sqlite3'), operation, sid, grant.token, attempt_id))
    worker.start()
    try:
        worker.join(60)
        assert worker.exitcode == 17
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(10)
        worker.close()
    assert list(conn.iterdump()) == before

@pytest.mark.parametrize('value', [None, True, 1.5, 0, -1])
def test_context_needs_verified_integer_limit(value):
    with pytest.raises(LedgerError):
        ledger(entry=rate_entry(context_limit_tokens=value))


def test_verified_context_is_part_of_pricing_and_enforced(env):
    _, doc, conn = env
    entry = rate_entry(context_limit_tokens=2048)
    assert pl.pricing_revision(entry) != pl.pricing_revision(rate_entry())
    with pytest.raises(LedgerError) as err:
        authorize(conn, doc, entry=entry)
    assert err.value.reason == 'CONTEXT_BOUND_EXCEEDED'
    assert dem_attempts(conn) == 0

@pytest.mark.parametrize('state,actual', [('settled', None), ('reconciled', None), ('released', None),
                                        ('over_reserve', None), ('reserved', 1), ('unresolved', 1)])
def test_corrupt_state_cannot_look_like_free_budget(env, state, actual):
    _, doc, conn = env
    res = authorize(conn, doc).reservation
    conn.execute('UPDATE ledger_attempts SET state=?, actual_micro_usd=? WHERE attempt_id=?',
                 (state, actual, res.attempt_id))
    with pytest.raises(LedgerError) as err:
        pl.budget_state(conn, now_ms=T0+5000)
    assert err.value.reason == 'LEDGER_STATE_CORRUPT'
    with pytest.raises(LedgerError):
        authorize(conn, doc, now_ms=T0+6000)
