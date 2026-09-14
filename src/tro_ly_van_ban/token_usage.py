"""Local Ollama request accounting; no prompts, replies or credentials are stored."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Context follows LangGraph's copied execution context, without a process-global sink.
_store = ContextVar("ollama_usage_store", default=None)
LOCAL_TZ = timezone(timedelta(hours=7))
MAX_METRIC = 10**12


@contextmanager
def capture_usage(store):
    token = _store.set(store)
    try:
        yield
    finally:
        _store.reset(token)


def metric(payload, key):
    value = payload.get(key) if isinstance(payload, dict) else None
    return value if type(value) is int and 0 <= value <= MAX_METRIC else None


@contextmanager
def measured_call(model):
    store = _store.get()
    payload = {}
    if store is None:
        yield payload
        return
    request_id = store.start(model)
    state = "failed"
    try:
        yield payload
        state = "received"
    finally:
        store.finish(request_id, payload, state)


class TokenUsage:
    def __init__(self, db):
        self.db = db
        with db() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS ollama_usage (
                    id TEXT PRIMARY KEY, created TEXT NOT NULL,
                    model TEXT NOT NULL, state TEXT NOT NULL,
                    input_tokens INTEGER, output_tokens INTEGER,
                    eval_ns INTEGER, total_ns INTEGER);
                CREATE INDEX IF NOT EXISTS ollama_usage_created ON ollama_usage(created);
            ''')

    def start(self, model):
        request_id = uuid4().hex
        with self.db() as conn:
            conn.execute("INSERT INTO ollama_usage(id,created,model,state) VALUES(?,?,?,'pending')",
                         (request_id, datetime.now(timezone.utc).isoformat(), str(model)[:200]))
        return request_id

    def finish(self, request_id, payload, state):
        with self.db() as conn:
            conn.execute('''UPDATE ollama_usage SET state=?,input_tokens=?,output_tokens=?,
                            eval_ns=?,total_ns=? WHERE id=? AND state='pending' ''',
                         (state, metric(payload, "prompt_eval_count"), metric(payload, "eval_count"),
                          metric(payload, "eval_duration"), metric(payload, "total_duration"), request_id))

    def summary(self, period="7d", now=None):
        if period not in {"today", "7d", "30d", "all"}:
            raise ValueError("Khoảng thời gian không hợp lệ")
        now = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days = {"today": 1, "7d": 7, "30d": 30, "all": 84}[period]
        start = midnight - timedelta(days=days - 1)
        since = "" if period == "all" else start.astimezone(timezone.utc).isoformat()
        until = now.astimezone(timezone.utc).isoformat()
        aggregate = '''COUNT(*) calls, SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens,
            SUM(CASE WHEN input_tokens IS NULL OR output_tokens IS NULL THEN 1 ELSE 0 END) incomplete,
            SUM(CASE WHEN state='failed' THEN 1 ELSE 0 END) failed,
            SUM(CASE WHEN state='pending' THEN 1 ELSE 0 END) pending,
            SUM(CASE WHEN eval_ns>0 AND output_tokens IS NOT NULL THEN output_tokens END) timed_tokens,
            SUM(CASE WHEN eval_ns>0 AND output_tokens IS NOT NULL THEN eval_ns END) timed_ns'''
        where = "WHERE created>=? AND created<=?"
        with self.db() as conn:
            # Cards, model breakdown and rows must describe the same DB snapshot.
            conn.execute("BEGIN")
            totals = dict(conn.execute(f"SELECT {aggregate} FROM ollama_usage {where}", (since, until)).fetchone())
            models = [dict(row) for row in conn.execute(
                f"SELECT model,{aggregate} FROM ollama_usage {where} GROUP BY model "
                "ORDER BY COALESCE(SUM(input_tokens),0)+COALESCE(SUM(output_tokens),0) DESC, model", (since, until))]
            recent = [dict(row) for row in conn.execute(
                f"SELECT * FROM ollama_usage {where} ORDER BY created DESC,id DESC LIMIT 50", (since, until))]
            activity = {row["day"]: dict(row) for row in conn.execute(
                "SELECT date(created,'+7 hours') day, COUNT(*) calls, SUM(input_tokens) input_tokens, "
                "SUM(output_tokens) output_tokens FROM ollama_usage WHERE created>=? AND created<=? GROUP BY day",
                (start.astimezone(timezone.utc).isoformat(), until))}
            first = conn.execute("SELECT MIN(created) FROM ollama_usage").fetchone()[0]
        series = []
        for offset in range(days):
            day = (start + timedelta(days=offset)).date().isoformat()
            series.append(activity.get(day, {"day": day, "calls": 0, "input_tokens": None, "output_tokens": None}))
        return {"period": period, "totals": totals, "models": models, "recent": recent,
                "activity": series, "first": first, "as_of": now.isoformat()}
