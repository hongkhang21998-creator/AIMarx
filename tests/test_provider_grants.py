"""GRANT-01 (#32): grant dùng một lần, lưu bền vững.

Quyết định: docs/GRANT_SCHEMA_OPTIONS.md (S1/S2, G1–G12, điều kiện 1–6 của Astra).
Toàn bộ dùng tài liệu giả lập, đồng hồ truyền vào, không mạng, không khoá API.

`FakeLedger` dưới đây chỉ có trong test, đứng thay ledger thật (chưa có). Không có
ledger thì `authorize_dispatch` từ chối — đó là thứ giữ cho hôm nay chưa có đường
nào tới mạng.
"""
import multiprocessing as mp
import os
import secrets
import sqlite3
from pathlib import Path

import pytest

from tro_ly_van_ban import provider_grants as pg
from tro_ly_van_ban import provider_ledger as pl
from tro_ly_van_ban import provider_snapshot as ps
from tro_ly_van_ban.provider_grants import Principal, RequestExists
from tro_ly_van_ban.provider_snapshot import AlreadyClaimed, SnapshotError, TrustedConfig
from tro_ly_van_ban.service import Service

SRC = ("UBND XÃ GIẢ LẬP\nSố: 07/UBND-VP\nGiả Lập, ngày 10/09/2026\n"
       "Đề nghị các thôn gửi báo cáo số hộ nghèo trước ngày 25/09/2026.\n"
       "Ghi chú: văn bản giả lập để thử nghiệm.\n").encode()
T0 = 1789113600000
UI_SECRET = b"U" * 32
OTHER_SECRET = b"O" * 32
CATALOGUE = ({"id": "ds-synthetic", "provider": "deepseek", "model": "synthetic-ds", "enabled": True},
             {"id": "local-qwen", "provider": "ollama", "model": "qwen3:0.6b", "enabled": True})


def make_config(**changes):
    base = {"models": CATALOGUE, "cloud_enabled": True,
            "revisions": {"adapter": "synthetic-adapter/0", "endpoint": "synthetic-endpoint/0", "pricing": "synthetic-pricing/0"},
            "settings": {"max_output_tokens": 2048, "temperature_milli": 0, "context_tokens": None}}
    base.update(changes)
    return TrustedConfig(**base)


# Mục rate card GIẢ LẬP tối thiểu, đủ hợp lệ để `settle` quyết toán bằng giá đã ghim.
FAKE_RATE_ENTRY = {
    "provider": "deepseek", "model": "synthetic-ds", "endpoint": "synthetic-endpoint/0", "currency": "USD",
    "input_micro_usd_per_mtok": 1_000_000, "output_micro_usd_per_mtok": 2_000_000,
    "request_fee_micro_usd": 0, "bound_method": "byte-level-verified",
    "bound_overhead_tokens_per_message": 32, "bound_overhead_tokens_fixed": 256,
    "billable_inputs_verified": True, "output_includes_reasoning_cap": True, "context_limit_tokens": 32768,
    "verified_at_ms": T0 - 86_400_000, "expires_at_ms": T0 + 5 * 86_400_000,
    "source": "https://vi-du.giaLap/gia",
}


def _fake_reserve(tx, snapshot, grant_id, now_ms, amount=1000):
    """Ghi một dòng sổ THẬT trong cùng transaction, rồi trả Reservation khớp dòng đó.

    Từ LEDGER-01 (P1), `authorize_dispatch` đối chiếu Reservation với dòng sổ thật, nên
    ledger giả trong test grant cũng phải ghi thật. Số học tiền là việc của
    `test_provider_ledger.py`; ở đây chỉ cần một khoản giữ hợp lệ.
    """
    pl.ensure_schema(tx.conn)
    attempt_id = secrets.token_hex(16)
    tx.conn.execute(
        "INSERT INTO ledger_attempts(attempt_id, snapshot_id, grant_id, provider, model, endpoint,"
        " pricing_revision, pricing_pinned, limits_revision, reserved_micro_usd, started_at_ms,"
        " deadline_ms, owner_id, owner_pid, owner_start_token, state)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'reserved')",
        (attempt_id, snapshot.snapshot_id, grant_id, "deepseek", "synthetic-ds", "synthetic-endpoint/0",
         snapshot.revisions["pricing"], ps.canonical_json(FAKE_RATE_ENTRY), "limits:test", amount, now_ms,
         now_ms + pl.DISPATCH_DEADLINE_MS, "0" * 32, 1, ""))
    return pl.Reservation(attempt_id=attempt_id, snapshot_id=snapshot.snapshot_id, grant_id=grant_id,
                          reserved_micro_usd=amount, pricing_revision=snapshot.revisions["pricing"],
                          limits_revision="limits:test", deadline_ms=now_ms + pl.DISPATCH_DEADLINE_MS)


class FakeLedger:
    """Chỉ trong test. Ghi một dòng vào bảng thăm dò trong CÙNG transaction."""

    def __init__(self, fail=False):
        self.fail = fail

    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms):
        ps._require_tx(tx)
        tx.conn.execute("CREATE TABLE IF NOT EXISTS ledger_probe(grant_id TEXT)")
        tx.conn.execute("INSERT INTO ledger_probe VALUES(?)", (grant_id,))
        if self.fail:
            raise RuntimeError("ledger hỏng")
        return _fake_reserve(tx, snapshot, grant_id, now_ms)


class CrashLedger:
    """Tiến trình chết hẳn giữa transaction, sau khi snapshot đã dispatching trong bộ nhớ."""

    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms):
        tx.conn.execute("CREATE TABLE IF NOT EXISTS ledger_probe(grant_id TEXT)")
        tx.conn.execute("INSERT INTO ledger_probe VALUES(?)", (grant_id,))
        os._exit(17)


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


def snapshot(conn, doc):
    return ps.prepare_snapshot(conn, extract(doc), config=make_config(), now_ms=T0).snapshot_id


def issue(conn, sid, secret=UI_SECRET, now_ms=T0 + 1000):
    return pg.issue_grant(conn, sid, principal=Principal(secret), now_ms=now_ms)


def authorize(conn, sid, token, secret=UI_SECRET, now_ms=T0 + 2000, config=None, ledger=None):
    return pg.authorize_dispatch(conn, sid, token, principal=Principal(secret), config=config or make_config(),
                                 now_ms=now_ms, ledger=FakeLedger() if ledger is None else ledger)


def grant_row(conn, grant_id):
    return conn.execute("SELECT state, end_reason, attempts_used FROM provider_grants WHERE grant_id=?", (grant_id,)).fetchone()


def snap_state(conn, sid):
    return conn.execute("SELECT state, end_reason FROM provider_snapshots WHERE snapshot_id=?", (sid,)).fetchone()


def probes(conn):
    has = conn.execute("SELECT count(*) FROM sqlite_master WHERE name='ledger_probe'").fetchone()[0]
    return conn.execute("SELECT count(*) FROM ledger_probe").fetchone()[0] if has else 0


# ---------- đường thành công ----------

def test_issue_then_authorize_consumes_once_and_dispatches(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    assert grant.expires_at_ms == T0 + 1000 + pg.GRANT_TTL_MS
    auth = authorize(conn, sid, grant.token)
    assert auth.grant_id == grant.grant_id and auth.snapshot.state == "dispatching"
    assert auth.snapshot.payload_bytes == ps.load_snapshot(conn, sid).payload_bytes
    assert grant_row(conn, grant.grant_id) == ("consumed", None, 1)
    assert probes(conn) == 1


# ---------- điều kiện 2: chưa có ledger thì không có đường tới mạng ----------

@pytest.mark.parametrize("ledger", [None, object(), "ledger"])
def test_without_a_ledger_nothing_is_consumed(env, ledger):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    with pytest.raises(SnapshotError) as err:
        pg.authorize_dispatch(conn, sid, grant.token, principal=Principal(UI_SECRET), config=make_config(),
                              now_ms=T0 + 2000, ledger=ledger)
    assert (err.value.code, err.value.reason) == ("LEDGER_UNAVAILABLE", "NO_LEDGER")
    assert grant_row(conn, grant.grant_id)[0] == "issued" and snap_state(conn, sid) == ("prepared", None)


def test_mcp_and_web_have_no_path_to_grants():
    src = Path(pg.__file__).parent
    for name in ("mcp_server.py", "web.py", "service.py"):
        assert "provider_grants" not in (src / name).read_text(encoding="utf-8"), name


# ---------- điều kiện 1, 4: cùng thành công hoặc cùng rollback ----------

def test_ledger_failure_rolls_back_snapshot_grant_and_ledger_together(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    with pytest.raises(RuntimeError, match="ledger hỏng"):
        authorize(conn, sid, grant.token, ledger=FakeLedger(fail=True))
    assert grant_row(conn, grant.grant_id)[0] == "issued"
    assert snap_state(conn, sid) == ("prepared", None)
    assert probes(conn) == 0
    assert authorize(conn, sid, grant.token).snapshot.state == "dispatching"  # thử lại được, không hỏng gì


def _crash_worker(db_path, sid, token):
    conn = sqlite3.connect(db_path, isolation_level=None)
    pg.authorize_dispatch(conn, sid, token, principal=Principal(UI_SECRET), config=make_config(),
                          now_ms=T0 + 2000, ledger=CrashLedger())


def test_process_crash_mid_transaction_leaves_no_half_state(env, tmp_path):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    proc = mp.get_context("spawn").Process(target=_crash_worker, args=(str(tmp_path / "state.sqlite3"), sid, grant.token))
    proc.start()
    proc.join(60)
    assert proc.exitcode == 17  # chết thật, giữa transaction
    fresh = sqlite3.connect(tmp_path / "state.sqlite3", isolation_level=None)  # như khởi động lại
    try:
        assert grant_row(fresh, grant.grant_id)[0] == "issued"
        assert snap_state(fresh, sid) == ("prepared", None)
        assert probes(fresh) == 0
        assert authorize(fresh, sid, grant.token).snapshot.state == "dispatching"
    finally:
        fresh.close()


# ---------- G10, điều kiện 4: không làm máy dò, không phát lại ----------

def test_second_authorize_returns_existing_state_without_replay(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    authorize(conn, sid, grant.token)
    with pytest.raises(RequestExists) as err:
        authorize(conn, sid, grant.token, now_ms=T0 + 3000)
    assert (err.value.grant_state, err.value.snapshot_state, err.value.code) == ("consumed", "dispatching", None)
    assert probes(conn) == 1  # không giữ ngân sách lần hai


@pytest.mark.parametrize("token", ["", "x" * 43, "!" * 43, None, 42, "a" * 42, "a" * 44])
def test_unknown_or_malformed_token_is_consent_required(env, token):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    issue(conn, sid)
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, token)
    assert (err.value.code, err.value.reason) == ("CONSENT_REQUIRED", "UNKNOWN_TOKEN")
    assert snap_state(conn, sid) == ("prepared", None)


def test_wrong_principal_even_after_consume_reveals_nothing(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, grant.token, secret=OTHER_SECRET)
    assert (err.value.code, err.value.reason) == ("CONSENT_REQUIRED", "PRINCIPAL_MISMATCH")
    assert grant_row(conn, grant.grant_id)[0] == "issued" and snap_state(conn, sid)[0] == "prepared"
    authorize(conn, sid, grant.token)
    with pytest.raises(SnapshotError) as err:  # đã dùng, nhưng sai principal thì không được biết điều đó
        authorize(conn, sid, grant.token, secret=OTHER_SECRET)
    assert type(err.value) is SnapshotError and err.value.code == "CONSENT_REQUIRED"


def test_token_for_one_snapshot_cannot_open_another(env):
    _, doc, conn = env
    a, b = snapshot(conn, doc), snapshot(conn, doc)
    grant_a = issue(conn, a)
    issue(conn, b)
    with pytest.raises(SnapshotError) as err:
        authorize(conn, b, grant_a.token)
    assert (err.value.code, err.value.reason) == ("CONSENT_REQUIRED", "SNAPSHOT_MISMATCH")
    assert snap_state(conn, a)[0] == snap_state(conn, b)[0] == "prepared"


def test_principal_cannot_be_forged_from_what_the_db_stores(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    stored = conn.execute("SELECT principal_sha256 FROM provider_grants").fetchone()[0]
    # Kẻ đọc được DB (MCP cùng file) chỉ có chuỗi này; dựng principal từ nó không khớp.
    for guess in (bytes.fromhex(stored), stored.encode(), stored.encode() * 2):
        with pytest.raises(SnapshotError) as err:
            authorize(conn, sid, grant.token, secret=guess if len(guess) >= 32 else guess * 2)
        assert err.value.reason == "PRINCIPAL_MISMATCH"
    # Kể cả bỏ qua hàm khởi tạo, nhét thẳng giá trị đọc từ DB vào đối tượng: DB giữ hash
    # của digest, nên digest giả = giá trị DB vẫn không khớp.
    forged = object.__new__(Principal)
    forged._digest = bytes.fromhex(stored)
    with pytest.raises(SnapshotError) as err:
        pg.authorize_dispatch(conn, sid, grant.token, principal=forged, config=make_config(), now_ms=T0 + 2000,
                              ledger=FakeLedger())
    assert err.value.reason == "PRINCIPAL_MISMATCH"
    assert grant_row(conn, grant.grant_id)[0] == "issued"


@pytest.mark.parametrize("secret", [b"short", "U" * 32, None, bytearray(b"U" * 32)])
def test_principal_needs_a_real_session_secret(secret):
    with pytest.raises(ValueError):
        Principal(secret)


def test_authorize_rejects_things_that_are_not_a_principal(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    for fake in ("ui:" + "0" * 64, Principal(UI_SECRET)._stored(), None):
        with pytest.raises(SnapshotError) as err:
            pg.authorize_dispatch(conn, sid, grant.token, principal=fake, config=make_config(), now_ms=T0 + 2000,
                                  ledger=FakeLedger())
        assert (err.value.code, err.value.reason) == ("INVALID_REQUEST", "PRINCIPAL")


# ---------- G5, G8: hạn và trạng thái chết được ghi cùng nhau ----------

def test_grant_expiry_boundaries(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid, now_ms=T0)
    assert authorize(conn, sid, grant.token, now_ms=T0 + pg.GRANT_TTL_MS - 1).snapshot.state == "dispatching"
    sid2 = snapshot(conn, doc)
    grant2 = issue(conn, sid2, now_ms=T0)
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid2, grant2.token, now_ms=T0 + pg.GRANT_TTL_MS)
    assert (err.value.code, err.value.reason) == ("CONSENT_EXPIRED", "GRANT_EXPIRED")
    assert grant_row(conn, grant2.grant_id)[:2] == ("expired", "EXPIRED")  # đã commit
    assert snap_state(conn, sid2) == ("prepared", None)
    with pytest.raises(SnapshotError) as err:  # lần sau vẫn nói hết hạn, không hồi sinh
        authorize(conn, sid2, grant2.token, now_ms=T0 + 1)
    assert err.value.code == "CONSENT_EXPIRED"


def test_clock_going_back_counts_as_expired(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid, now_ms=T0 + 5000)
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, grant.token, now_ms=T0 + 4999)
    assert err.value.code == "CONSENT_EXPIRED"


def test_grant_never_outlives_its_snapshot(env):
    _, doc, conn = env
    sid = ps.prepare_snapshot(conn, extract(doc), config=make_config(), now_ms=T0, ttl_ms=2 * 60 * 1000).snapshot_id
    grant = issue(conn, sid, now_ms=T0 + 1000)
    assert grant.expires_at_ms == T0 + 2 * 60 * 1000


def test_snapshot_death_voids_grant_in_the_same_commit(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, grant.token, config=make_config(settings={"max_output_tokens": 1024, "temperature_milli": 0, "context_tokens": None}))
    assert (err.value.code, err.value.reason) == ("STALE_REQUEST", "REVISION_CHANGED")
    assert snap_state(conn, sid) == ("invalidated", "REVISION_CHANGED")
    assert grant_row(conn, grant.grant_id)[:2] == ("voided", "REVISION_CHANGED")
    assert probes(conn) == 0
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, grant.token)
    assert (err.value.code, err.value.reason) == ("CONSENT_REQUIRED", "GRANT_VOIDED")


def test_label_change_after_consent_voids_grant(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    conn.execute("UPDATE documents SET classification='internal' WHERE id=?", (doc,))
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, grant.token)
    assert err.value.reason == "CLASSIFICATION_CHANGED"
    assert grant_row(conn, grant.grant_id)[0] == "voided"


def test_replaced_snapshot_record_does_not_match_the_grant(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    # Thay bản ghi và hash khớp nhau: snapshot tự nó vẫn "toàn vẹn", nhưng không phải thứ người dùng đã xem.
    record = conn.execute("SELECT record FROM provider_snapshots WHERE snapshot_id=?", (sid,)).fetchone()[0]
    swapped = bytes(record).replace(b'"payload_size":3488', b'"payload_size":3487')
    conn.execute("UPDATE provider_snapshots SET record=?, record_sha256=? WHERE snapshot_id=?",
                 (swapped, ps._sha(swapped), sid))
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, grant.token)
    assert (err.value.code, err.value.reason) == ("CONSENT_REQUIRED", "BINDING_MISMATCH")
    assert grant_row(conn, grant.grant_id)[:2] == ("voided", "BINDING_MISMATCH")
    assert snap_state(conn, sid)[0] == "prepared"


def test_ended_snapshot_voids_its_grant(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    ps.cancel(conn, sid, now_ms=T0 + 1500)
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, grant.token)
    assert (err.value.code, err.value.reason) == ("CONSENT_REQUIRED", "SNAPSHOT_CANCELLED")
    assert grant_row(conn, grant.grant_id)[0] == "voided"


# ---------- G2, G11, điều kiện 5: bấm hai lần ----------

def test_double_click_issue_returns_existing_state_not_sqlite_error(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    first = issue(conn, sid)
    with pytest.raises(RequestExists) as err:
        issue(conn, sid, now_ms=T0 + 1100)
    assert (err.value.grant_state, err.value.snapshot_state) == ("issued", "prepared")
    authorize(conn, sid, first.token)
    with pytest.raises(RequestExists) as err:
        issue(conn, sid, now_ms=T0 + 3000)
    assert (err.value.grant_state, err.value.snapshot_state) == ("consumed", "dispatching")
    assert conn.execute("SELECT count(*) FROM provider_grants").fetchone()[0] == 1


def test_issue_only_for_live_cloud_snapshots(env):
    _, doc, conn = env
    local = ps.prepare_snapshot(conn, extract(doc, model_id="local-qwen"), config=make_config(cloud_enabled=False),
                                now_ms=T0).snapshot_id
    with pytest.raises(SnapshotError) as err:
        issue(conn, local)
    assert (err.value.code, err.value.reason) == ("INVALID_REQUEST", "NOT_CONSENT_SNAPSHOT")
    expired = snapshot(conn, doc)
    with pytest.raises(SnapshotError) as err:
        issue(conn, expired, now_ms=T0 + ps.TTL_DEFAULT_MS)
    assert err.value.code == "CONSENT_EXPIRED"
    cancelled = snapshot(conn, doc)
    ps.cancel(conn, cancelled, now_ms=T0 + 500)
    with pytest.raises(AlreadyClaimed):
        issue(conn, cancelled)
    with pytest.raises(SnapshotError):
        issue(conn, "0" * 32)
    pg.ensure_schema(conn)  # mọi lần cấp đều rollback, kể cả lệnh tạo bảng
    assert conn.execute("SELECT count(*) FROM provider_grants").fetchone()[0] == 0


# ---------- hai tiến trình ----------

class SlowLedger(FakeLedger):
    """Nới khe ĐÚNG chỗ: bước ledger nằm giữa lúc claim snapshot và lúc tiêu thụ grant.

    Ngủ trước khi ghi, để một bản cài đặt lỡ commit trước bước này không còn giữ khoá
    lúc ngủ. Nới khe ở evaluate_policy (trước claim) thì đột biến "kiểm snapshot và
    tiêu thụ grant ở hai transaction" lọt qua test này — đã thử.
    """

    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms):
        import time
        time.sleep(0.02)
        return super().reserve_locked(tx, snapshot=snapshot, grant_id=grant_id, now_ms=now_ms)


def _race_worker(db_path, jobs, barrier, out):
    conn = sqlite3.connect(db_path, isolation_level=None)
    results = []
    for sid, token in jobs:
        barrier.wait(30)
        try:
            authorize(conn, sid, token, ledger=SlowLedger())
            results.append("won")
        except RequestExists as err:
            results.append(f"exists:{err.grant_state}:{err.snapshot_state}")
        except Exception as err:  # noqa: BLE001 — cần thấy cả OperationalError
            results.append("error:" + type(err).__name__)
    conn.close()
    out.put(results)


def test_two_processes_authorize_the_same_token_exactly_once(env, tmp_path):
    _, doc, conn = env
    jobs = []
    for _ in range(15):
        sid = snapshot(conn, doc)
        jobs.append((sid, issue(conn, sid).token))
    ctx = mp.get_context("spawn")
    barrier, out = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_race_worker, args=(str(tmp_path / "state.sqlite3"), jobs, barrier, out)) for _ in range(2)]
    for w in workers:
        w.start()
    a, b = out.get(timeout=120), out.get(timeout=120)
    for w in workers:
        w.join(30)
    for i, pair in enumerate(zip(a, b)):
        assert sorted(pair) == ["exists:consumed:dispatching", "won"], (i, pair)
    assert probes(conn) == 15  # đúng một lần giữ ngân sách cho mỗi grant


def _issue_worker(db_path, sid, barrier, out):
    conn = sqlite3.connect(db_path, isolation_level=None)
    barrier.wait(30)
    try:
        issue(conn, sid)
        out.put("issued")
    except RequestExists as err:
        out.put("exists:" + err.grant_state)
    except Exception as err:  # noqa: BLE001
        out.put("error:" + type(err).__name__)
    conn.close()


def test_two_processes_issue_for_one_snapshot_get_one_grant(env, tmp_path):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    ctx = mp.get_context("spawn")
    barrier, out = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_issue_worker, args=(str(tmp_path / "state.sqlite3"), sid, barrier, out)) for _ in range(2)]
    for w in workers:
        w.start()
    results = sorted([out.get(timeout=120), out.get(timeout=120)])
    for w in workers:
        w.join(30)
    assert results == ["exists:issued", "issued"]
    assert conn.execute("SELECT count(*) FROM provider_grants").fetchone()[0] == 1


# ---------- khởi động lại không hồi sinh ----------

def test_restart_never_resurrects_a_consumed_grant(env, tmp_path):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    authorize(conn, sid, grant.token)
    conn.close()
    reopened = sqlite3.connect(tmp_path / "state.sqlite3", isolation_level=None)
    try:
        for attempt in (lambda: authorize(reopened, sid, grant.token, now_ms=T0 + 9000),
                        lambda: issue(reopened, sid, now_ms=T0 + 9000),
                        lambda: pg.revoke(reopened, grant.grant_id, principal=Principal(UI_SECRET), now_ms=T0 + 9000)):
            with pytest.raises(RequestExists) as err:
                attempt()
            assert err.value.grant_state == "consumed"
        assert grant_row(reopened, grant.grant_id) == ("consumed", None, 1)
    finally:
        reopened.close()


# ---------- thu hồi ----------

def test_revoke_before_use_cancels_snapshot_and_blocks_use(env):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    with pytest.raises(SnapshotError) as err:  # chỉ người cấp mới thu hồi được
        pg.revoke(conn, grant.grant_id, principal=Principal(OTHER_SECRET), now_ms=T0 + 1500)
    assert err.value.reason == "UNKNOWN_GRANT"
    pg.revoke(conn, grant.grant_id, principal=Principal(UI_SECRET), now_ms=T0 + 1500)
    assert grant_row(conn, grant.grant_id)[:2] == ("revoked", "REVOKED")
    assert snap_state(conn, sid) == ("cancelled", "GRANT_REVOKED")
    with pytest.raises(SnapshotError) as err:
        authorize(conn, sid, grant.token)
    assert (err.value.code, err.value.reason) == ("CONSENT_REQUIRED", "GRANT_REVOKED")


def test_revoke_all_leaves_consumed_grants_alone(env):
    _, doc, conn = env
    used = snapshot(conn, doc)
    used_grant = issue(conn, used)
    authorize(conn, used, used_grant.token)
    pending = [snapshot(conn, doc) for _ in range(3)]
    grants = [issue(conn, s) for s in pending]
    assert pg.revoke_all_unconsumed(conn, now_ms=T0 + 5000) == 3
    assert grant_row(conn, used_grant.grant_id)[0] == "consumed" and snap_state(conn, used)[0] == "dispatching"
    for s, g in zip(pending, grants):
        assert grant_row(conn, g.grant_id)[0] == "revoked" and snap_state(conn, s)[0] == "cancelled"


# ---------- G12, điều kiện 6: lưu giữ ----------

def test_purge_keeps_consumed_and_deletes_only_never_sent_after_30_days(env):
    _, doc, conn = env
    used = snapshot(conn, doc)
    used_grant = issue(conn, used)
    auth = authorize(conn, used, used_grant.token)
    # P2 (#43): snapshot cloud đã giữ tiền chỉ đóng được qua sổ. `ps.finish` thẳng tay
    # nay là SETTLEMENT_REQUIRED, nên đi đúng đường: quyết toán rồi snapshot mới failed.
    pl.settle(conn, auth.reservation.attempt_id, usage=pl.Usage(input_tokens=1, output_tokens=1),
              outcome="failed", now_ms=T0 + 3000)
    revoked_sid = snapshot(conn, doc)
    revoked = issue(conn, revoked_sid)
    pg.revoke(conn, revoked.grant_id, principal=Principal(UI_SECRET), now_ms=T0 + 3000)
    stale_sid = snapshot(conn, doc)
    stale = issue(conn, stale_sid)                                      # không ai dùng, tự hết hạn
    assert pg.purge_grants(conn, now_ms=T0 + pg.RETAIN_MS) == 0         # chưa đủ 30 ngày
    assert grant_row(conn, stale.grant_id)[0] == "expired"
    assert pg.purge_grants(conn, now_ms=T0 + 3000 + pg.RETAIN_MS + pg.GRANT_TTL_MS) == 2
    assert grant_row(conn, used_grant.grant_id)[0] == "consumed"
    # Grant đã dùng không bao giờ bị xoá, kể cả khi có mốc thời gian cũ tới đâu.
    conn.execute("UPDATE provider_grants SET ended_at_ms=0 WHERE grant_id=?", (used_grant.grant_id,))
    assert pg.purge_grants(conn, now_ms=T0 + 10 * pg.RETAIN_MS) == 0
    assert grant_row(conn, used_grant.grant_id)[0] == "consumed" and grant_row(conn, stale.grant_id) is None


# ---------- không rò token, principal ----------

def test_token_and_secret_never_leak(env, tmp_path, caplog):
    _, doc, conn = env
    sid = snapshot(conn, doc)
    grant = issue(conn, sid)
    assert grant.token not in repr(grant) and "U" * 32 not in repr(Principal(UI_SECRET))
    errors = []
    for attempt in (lambda: authorize(conn, sid, grant.token, secret=OTHER_SECRET),
                    lambda: authorize(conn, "f" * 32, grant.token),
                    lambda: issue(conn, sid),
                    lambda: pg.authorize_dispatch(conn, sid, grant.token, principal=Principal(UI_SECRET),
                                                  config=make_config(), now_ms=T0 + 2000, ledger=None)):
        with pytest.raises(SnapshotError) as err:
            attempt()
        errors.append(err.value)
    authorize(conn, sid, grant.token)
    with pytest.raises(RequestExists) as err:
        authorize(conn, sid, grant.token)
    errors.append(err.value)
    stored = conn.execute("SELECT principal_sha256 FROM provider_grants").fetchone()[0]
    for error in errors:
        text = f"{error!s} {error!r} {error.args} {error.reason}"
        assert grant.token not in text and stored not in text
    assert grant.token not in caplog.text
    conn.execute("PRAGMA wal_checkpoint")
    raw = (tmp_path / "state.sqlite3").read_bytes()
    assert grant.token.encode() not in raw and UI_SECRET not in raw  # DB chỉ có hash
