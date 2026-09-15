"""One local AIMarx façade shared by HTTP and MCP."""

from __future__ import annotations

import httpx
import os

from .credentials import CredentialStore, DEFAULT_PROVIDERS, ProviderDefinition
from .provider_adapter import ProviderAdapter
from .provider_gateway import ProviderGateway
from .token_usage import capture_usage, measured_call
from .local_config import MAX_LOCAL_CONTEXT


class AimarxError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Aimarx:
    def __init__(self, service, *, credential_backend=None, local_transport=None, provider_transport=None):
        self.service = service
        definitions = (ProviderDefinition("local-qwen", "ollama", service.model,
                       "http://127.0.0.1:11434", True, 60, 120), *DEFAULT_PROVIDERS[1:])
        self.credentials = CredentialStore(service.db, backend=credential_backend, definitions=definitions)
        # The launch configuration owns the local model, including after an upgrade.
        with service.db() as conn:
            conn.execute("UPDATE providers SET model=?,provider='ollama',endpoint=? WHERE id='local-qwen'",
                         (service.model, "http://127.0.0.1:11434"))
        self.local_only = os.getenv("TLVB_LOCAL_ONLY", "0") == "1"
        self.provider_adapter = ProviderAdapter(self.credentials, transport=provider_transport,
                                                local_only=self.local_only)
        self.provider_gateway = ProviderGateway(service, self.credentials, self.provider_adapter)
        self.local_transport = local_transport

    def list_models(self) -> list[dict]:
        return [{"id": row["id"], "provider": row["provider"], "model": row["model"],
                 "enabled": row["enabled"] and (not self.local_only or row["provider"] == "ollama"),
                 "data_destination": "local" if row["provider"] == "ollama" else "cloud"}
                for row in self.credentials.list_public()]

    def ask(self, message: str, model_id: str | None = None) -> dict:
        if type(message) is not str or not message.strip() or len(message) > 32_768:
            raise ValueError("Nội dung yêu cầu không hợp lệ")
        chosen = model_id or "local-qwen"
        if type(chosen) is not str:
            raise ValueError("Model không hợp lệ")
        found = next((row for row in self.credentials.list_public() if row["id"] == chosen), None)
        if found is None or not found["enabled"]:
            raise AimarxError("POLICY_DENIED", "Model chưa được bật")
        if found["provider"] != "ollama":
            raise AimarxError("CONSENT_REQUIRED", "Yêu cầu cloud phải được xác nhận trong giao diện local")
        return self.local_chat([{"role": "system", "content": (
            "Bạn là AIMarx local. Trả lời ngắn gọn bằng tiếng Việt. "
            "Lượt trò chuyện này không có công cụ. Không tuyên bố đã thực hiện thao tác.")},
            {"role": "user", "content": message.strip()}])

    def local_chat(self, messages: list[dict], *, schema: dict | None = None, max_tokens=384) -> dict:
        found = self.credentials.get_public("local-qwen")
        if (not found["enabled"] or found["provider"] != "ollama"
                or found["endpoint"] != "http://127.0.0.1:11434"
                or found["model"] != self.service.model):
            raise AimarxError("POLICY_DENIED", "Cấu hình model local không khớp runtime")
        payload = {"model": self.service.model, "stream": False, "keep_alive": "5m",
                   "options": {"temperature": 0, "num_ctx": MAX_LOCAL_CONTEXT, "num_predict": min(max_tokens, 768)},
                   "messages": messages}
        if schema is not None:
            payload["format"] = schema
        if not self.service.lock.acquire(blocking=False):
            raise AimarxError("LOCAL_BUSY", "Qwen đang xử lý một yêu cầu; vui lòng thử lại sau")
        usage_payload = {}
        try:
            with capture_usage(self.service.token_usage), measured_call(found["model"]) as usage_payload:
                timeout = httpx.Timeout(found["timeout_seconds"], connect=5, write=10, pool=2)
                with httpx.Client(timeout=timeout, transport=self.local_transport,
                                  trust_env=False, follow_redirects=False) as client:
                    response = client.post("http://127.0.0.1:11434/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                if type(data) is not dict or type(data.get("message")) is not dict:
                    raise ValueError
                content = data["message"].get("content")
                if type(content) is not str or not content.strip():
                    raise ValueError
                for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration",
                            "prompt_eval_duration", "eval_duration"):
                    value = data.get(key)
                    if type(value) is int and value >= 0:
                        usage_payload[key] = value
        except (httpx.HTTPError, ValueError, TypeError):
            raise AimarxError("LOCAL_MODEL_UNAVAILABLE", "SLM local chưa sẵn sàng hoặc trả dữ liệu không hợp lệ") from None
        finally:
            self.service.lock.release()
        return {"model_id": "local-qwen", "model": self.service.model, "provider": "ollama", "destination": "local",
                "content": content, "usage": {
                    "input_tokens": usage_payload.get("prompt_eval_count"),
                    "output_tokens": usage_payload.get("eval_count")}}

    def run_agent(self, message: str, document_id: str | None = None) -> dict:
        from .local_agent import run_agent
        return run_agent(self, message, document_id)

    def usage(self, period="7d") -> dict:
        return self.service.token_usage.summary(period)

    def test_provider(self, provider_id: str) -> dict:
        return self.provider_adapter.test_credential(provider_id)
