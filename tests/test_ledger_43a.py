"""43a supplements #43 using only synthetic config and isolated SQLite databases."""
import pytest

from test_provider_ledger import (
    Principal, UI_SECRET, T0, authorize, env, ms, pl, ps, rate_entry,
)


def test_unresolved_replay_conflicting_reason_is_rejected_without_mutation(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    attempt = auth.reservation.attempt_id
    pl.mark_unresolved(conn, attempt, reason="TRANSPORT_TIMEOUT", now_ms=T0 + 3000)
    before = conn.execute("SELECT * FROM ledger_events").fetchall()
    high = conn.execute("SELECT high_water_ms FROM ledger_clock").fetchone()[0]
    with pytest.raises(pl.LedgerError) as exc:
        pl.mark_unresolved(conn, attempt, reason="USAGE_MISSING", now_ms=T0 + 4000)
    assert exc.value.reason == "UNRESOLVED_CONFLICT"
    assert conn.execute("SELECT * FROM ledger_events").fetchall() == before
    assert conn.execute("SELECT high_water_ms FROM ledger_clock").fetchone()[0] == high
    assert conn.execute("SELECT end_reason FROM ledger_attempts").fetchone()[0] == "TRANSPORT_TIMEOUT"


def test_unresolved_same_reason_replay_adds_no_event(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    for offset in (3000, 4000):
        pl.mark_unresolved(conn, auth.reservation.attempt_id, reason="TRANSPORT_TIMEOUT", now_ms=T0 + offset)
    assert conn.execute("SELECT COUNT(*) FROM ledger_events WHERE to_state='unresolved'").fetchone()[0] == 1


@pytest.mark.parametrize("boundary", ["2026-09-13T00:00:00+07:00", "2026-10-01T00:00:00+07:00"])
@pytest.mark.parametrize("state", ["reserved", "unresolved", "over_reserve", "settled", "reconciled", "released"])
def test_every_ledger_state_contributes_once_across_calendar_boundary(env, boundary, state):
    _, doc, conn = env
    after = ms(boundary) + 1000
    start = ms(boundary) - 10000
    auth = authorize(conn, doc, now_ms=start,
                     entry=rate_entry(verified_at_ms=start - 86400000, expires_at_ms=after + 86400000))
    attempt = auth.reservation.attempt_id
    reserved = auth.reservation.reserved_micro_usd
    actual = None
    if state == "unresolved":
        pl.mark_unresolved(conn, attempt, reason="TRANSPORT_TIMEOUT", now_ms=after)
    elif state in ("settled", "over_reserve"):
        usage = pl.Usage(input_tokens=10 if state == "settled" else reserved + 1, output_tokens=10)
        actual = usage.input_tokens + 2 * usage.output_tokens
        assert pl.settle(conn, attempt, usage=usage, outcome="failed", now_ms=after) == state
    elif state == "reconciled":
        pl.mark_unresolved(conn, attempt, reason="TRANSPORT_TIMEOUT", now_ms=after)
        actual = 17
        pl.reconcile(conn, attempt, principal=Principal(UI_SECRET), actual_micro_usd=actual,
                     evidence="Synthetic billing record 43a", now_ms=after + 1)
        pl.reconcile(conn, attempt, principal=Principal(UI_SECRET), actual_micro_usd=actual,
                     evidence="Synthetic billing record 43a", now_ms=after + 2)
    elif state == "released":
        proof = pl.UnsentProof(stage="dns", error_class="SyntheticDNS", bytes_sent=0)
        pl.release_unsent(conn, attempt, proof=proof, now_ms=after)
        actual = 0
    old = pl.budget_state(conn, now_ms=start + 2000)
    new = pl.budget_state(conn, now_ms=after + 2)
    contribution = reserved if state in ("reserved", "unresolved") else actual
    for period in ("day_micro_usd", "month_micro_usd"):
        assert old[period] == contribution
        old_period = pl._bucket(start)[0 if period.startswith("day") else 2]
        new_period = pl._bucket(after)[0 if period.startswith("day") else 2]
        expected = contribution if state in pl.PENDING_STATES or old_period == new_period else 0
        assert new[period] == expected


def test_unresolved_event_failure_rolls_back_clock_money_and_snapshot(env):
    _, doc, conn = env
    auth = authorize(conn, doc)
    before = list(conn.iterdump())
    conn.execute("""CREATE TEMP TRIGGER fail_unresolved BEFORE INSERT ON ledger_events
                    WHEN NEW.to_state='unresolved' BEGIN SELECT RAISE(ABORT, '43a fault'); END""")
    with pytest.raises(ps.SnapshotError) as exc:
        pl.mark_unresolved(conn, auth.reservation.attempt_id, reason="TRANSPORT_TIMEOUT", now_ms=T0 + 3000)
    assert exc.value.reason == "DB_ERROR"
    conn.execute("DROP TRIGGER fail_unresolved")
    assert list(conn.iterdump()) == before
    pl.mark_unresolved(conn, auth.reservation.attempt_id, reason="TRANSPORT_TIMEOUT", now_ms=T0 + 3000)
