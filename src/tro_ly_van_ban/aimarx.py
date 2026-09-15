"""One local AIMarx façade shared by HTTP and MCP."""

from __future__ import annotations

import httpx

from .credentials import CredentialStore, DEFAULT_PROVIDERS, ProviderDefinition
from .provider_adapter import ProviderAdapter
from .provider_gateway import ProviderGateway
from .token_usage import capture_usage, measured_call


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
        self.provider_adapter = ProviderAdapter(self.credentials, transport=provider_transport)
        self.provider_gateway = ProviderGateway(service, self.credentials, self.provider_adapter)
        self.local_transport = local_transport

    def list_models(self) -> list[dict]:
        return [{"id": row["id"], "provider": row["provider"], "model": row["model"],
                 "enabled": row["enabled"],
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
        payload = {"model": found["model"], "stream": False, "think": False,
                   "options": {"temperature": 0, "num_predict": 1024},
                   "messages": [{"role": "system", "content": (
                       "Bạn là AIMarx local. Hãy phân loại yêu cầu, nêu bước xử lý phù hợp và trả lời ngắn gọn. "
                       "Không được tự gọi cloud, tự cấp quyền hoặc tuyên bố đã thực hiện công cụ.")},
                                {"role": "user", "content": message.strip()}]}
        usage_payload = {}
        try:
            with capture_usage(self.service.token_usage), measured_call(found["model"]) as usage_payload:
                timeout = httpx.Timeout(found["timeout_seconds"], connect=5, write=10, pool=2)
                with httpx.Client(timeout=timeout, transport=self.local_transport,
                                  trust_env=False, follow_redirects=False) as client:
                    response = client.post(found["endpoint"] + "/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                if type(data) is not dict or type(data.get("message")) is not dict:
                    raise ValueError
                content = data["message"].get("content")
                if type(content) is not str or not content.strip():
                    raise ValueError
                usage_payload.update(data)
        except (httpx.HTTPError, ValueError, TypeError):
            raise AimarxError("LOCAL_MODEL_UNAVAILABLE", "SLM local chưa sẵn sàng hoặc trả dữ liệu không hợp lệ") from None
        return {"model_id": chosen, "provider": "ollama", "destination": "local",
                "content": content, "usage": {
                    "input_tokens": usage_payload.get("prompt_eval_count"),
                    "output_tokens": usage_payload.get("eval_count")}}

    def usage(self, period="7d") -> dict:
        return self.service.token_usage.summary(period)

    def test_provider(self, provider_id: str) -> dict:
        return self.provider_adapter.test_credential(provider_id)
