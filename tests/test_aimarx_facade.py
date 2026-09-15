import json

import httpx
import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tro_ly_van_ban.aimarx import Aimarx, AimarxError
from tro_ly_van_ban.credentials import CredentialStore
from tro_ly_van_ban.mcp_server import create_mcp
from tro_ly_van_ban.provider_adapter import ProviderAdapter, ProviderAdapterError
from tro_ly_van_ban import provider_ledger
from tro_ly_van_ban.service import Service
from tro_ly_van_ban.web import create_app


SENTINEL = "sk-test-never-store-me-9F2A"
T0 = 1_789_098_000_000


class MemoryVault:
    def __init__(self):
        self.values = {}

    def get(self, service, username):
        return self.values.get((service, username))

    def set(self, service, username, secret):
        self.values[(service, username)] = secret

    def delete(self, service, username):
        self.values.pop((service, username), None)


@pytest.fixture
def env(tmp_path):
    service = Service(tmp_path, "demo")
    vault = MemoryVault()
    service.aimarx = Aimarx(service, credential_backend=vault)
    return service, vault, tmp_path


def test_secret_only_goes_to_vault_and_public_views_never_return_it(env):
    service, vault, root = env
    public = service.aimarx.credentials.set_secret("deepseek-chat", SENTINEL)
    assert vault.values
    assert SENTINEL not in str(public)
    assert SENTINEL.encode() not in (root / "state.sqlite3").read_bytes()
    assert public["key_fingerprint"].startswith("sha256:") and public["has_credential"]


def test_revoke_deletes_vault_value_metadata_and_disables_provider(env):
    service, vault, _ = env
    store = service.aimarx.credentials
    store.set_secret("openai-mini", SENTINEL)
    store.set_enabled("openai-mini", True)
    result = store.revoke("openai-mini")
    assert not vault.values and not result["has_credential"] and not result["enabled"]


def test_local_chat_is_counted_and_cloud_never_falls_through(env):
    service, _, _ = env

    def local(request):
        assert request.url.host == "127.0.0.1"
        return httpx.Response(200, json={"message": {"content": "local only"},
            "prompt_eval_count": 12, "eval_count": 4})

    service.aimarx.local_transport = httpx.MockTransport(local)
    assert service.aimarx.ask("phân loại việc này")["content"] == "local only"
    assert service.aimarx.usage("all")["totals"]["input_tokens"] == 12
    service.aimarx.credentials.set_secret("deepseek-chat", SENTINEL)
    service.aimarx.credentials.set_enabled("deepseek-chat", True)
    with pytest.raises(AimarxError) as exc:
        service.aimarx.ask("không được gửi", "deepseek-chat")
    assert exc.value.code == "CONSENT_REQUIRED"


def test_provider_adapter_uses_allowlist_and_never_echoes_secret(env):
    service, _, _ = env
    service.aimarx.credentials.set_secret("deepseek-chat", SENTINEL)

    def denied(request):
        assert request.url == "https://api.deepseek.com/v1/models"
        assert request.headers["authorization"] == "Bearer " + SENTINEL
        return httpx.Response(401, text=SENTINEL)

    adapter = ProviderAdapter(service.aimarx.credentials, transport=httpx.MockTransport(denied))
    with pytest.raises(ProviderAdapterError) as exc:
        adapter.test_credential("deepseek-chat")
    assert exc.value.code == "AUTH_FAILED" and SENTINEL not in str(exc.value)


def test_cloud_gateway_requires_preview_consent_ledger_and_settles(env):
    service, _, root = env
    store = service.aimarx.credentials
    store.set_secret("deepseek-chat", SENTINEL)
    store.set_enabled("deepseek-chat", True)
    entry = {"provider": "deepseek", "model": "deepseek-chat", "endpoint": "https://api.deepseek.com",
        "currency": "USD", "input_micro_usd_per_mtok": 1_000_000,
        "output_micro_usd_per_mtok": 2_000_000, "request_fee_micro_usd": 0,
        "bound_method": "byte-level-verified", "bound_overhead_tokens_per_message": 32,
        "bound_overhead_tokens_fixed": 256, "billable_inputs_verified": True,
        "output_includes_reasoning_cap": True, "context_limit_tokens": 32768,
        "verified_at_ms": T0 - 1000, "expires_at_ms": T0 + 86_400_000,
        "source": "https://example.invalid/test-rate-card"}
    config = {"schema": provider_ledger.RATE_CARD_SCHEMA, "entries": [entry],
        "limits": {"schema": provider_ledger.LIMITS_SCHEMA, "request_micro_usd": 1_000_000,
                   "day_micro_usd": 1_000_000, "month_micro_usd": 1_000_000}}
    config_path = root / "provider-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    gateway = service.aimarx.provider_gateway
    gateway.config_path = config_path
    gateway.clock = lambda: T0

    calls = []
    def cloud(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "cloud result"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    service.aimarx.provider_adapter.transport = httpx.MockTransport(cloud)

    preview = gateway.prepare_chat("soạn bản nháp", "deepseek-chat", "synthetic")
    assert calls == [] and preview["classification"] == "synthetic"
    result = gateway.confirm_and_execute(preview["snapshot_id"], "deepseek-chat",
                                         principal_secret=b"u" * 32)
    assert result["content"] == "cloud result" and result["ledger_state"] == "settled"
    assert len(calls) == 1 and SENTINEL not in str(result)


def test_http_api_and_mcp_expose_no_credential_parameter(env):
    service, _, _ = env
    service.aimarx.local_transport = httpx.MockTransport(lambda request: httpx.Response(
        200, json={"message": {"content": "ok"}, "prompt_eval_count": 1, "eval_count": 1}))
    web = TestClient(create_app(service), base_url="http://127.0.0.1")
    providers = web.get("/v1/providers").json()["providers"]
    assert SENTINEL not in str(providers)
    assert web.post("/v1/chat", json={"message": "xin chào"}).json()["destination"] == "local"

    async def inspect():
        async with Client(create_mcp(service)) as client:
            tools = await client.list_tools()
            schemas = {tool.name: tool.input_schema for tool in tools}
            assert set(schemas) == {"ask_aimarx", "list_models", "get_usage", "read_document", "get_evidence"}
            assert "credential" not in str(schemas).lower() and "api_key" not in str(schemas).lower()
    import asyncio
    asyncio.run(inspect())
