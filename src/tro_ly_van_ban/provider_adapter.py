"""Narrow provider adapters. Credentials never enter caller parameters or results."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

import httpx


ALLOWED_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com",
}


class ProviderAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ProviderAdapter:
    def __init__(self, credentials, *, transport=None, clock=time.monotonic):
        self.credentials = credentials
        self.transport = transport
        self.clock = clock
        self._calls = defaultdict(deque)
        self._lock = threading.Lock()

    def _limit(self, provider_id: str, rpm: int):
        now = self.clock()
        with self._lock:
            calls = self._calls[provider_id]
            while calls and calls[0] <= now - 60:
                calls.popleft()
            if len(calls) >= rpm:
                raise ProviderAdapterError("RATE_LIMITED", "Đã đạt hạn mức request của provider")
            calls.append(now)

    def _client(self, timeout_seconds: int):
        timeout = httpx.Timeout(timeout_seconds, connect=min(5, timeout_seconds),
                                write=min(10, timeout_seconds), pool=min(2, timeout_seconds))
        return httpx.Client(timeout=timeout, transport=self.transport, trust_env=False, follow_redirects=False)

    def test_credential(self, provider_id: str) -> dict:
        meta = self.credentials.get_public(provider_id)
        provider = meta["provider"]
        if provider not in ALLOWED_ENDPOINTS or meta["endpoint"] != ALLOWED_ENDPOINTS[provider]:
            raise ProviderAdapterError("POLICY_DENIED", "Endpoint provider không nằm trong allowlist")
        self._limit(provider_id, meta["requests_per_minute"])
        secret = self.credentials.secret_for_backend(provider_id)
        try:
            with self._client(meta["timeout_seconds"]) as client:
                response = client.get(meta["endpoint"] + "/v1/models",
                                      headers={"Authorization": "Bearer " + secret})
            if response.status_code in {401, 403}:
                raise ProviderAdapterError("AUTH_FAILED", "API key bị provider từ chối")
            if response.status_code == 429:
                raise ProviderAdapterError("RATE_LIMITED", "Provider đang giới hạn request")
            if response.status_code >= 400:
                raise ProviderAdapterError("PROVIDER_ERROR", "Provider không xác nhận được API key")
            return {"provider_id": provider_id, "status": "ok"}
        except ProviderAdapterError:
            raise
        except httpx.TimeoutException:
            raise ProviderAdapterError("TIMEOUT", "Provider không phản hồi trong thời hạn") from None
        except httpx.HTTPError:
            raise ProviderAdapterError("PROVIDER_ERROR", "Không kết nối được provider") from None

    def chat(self, provider_id: str, messages: list[dict], *, max_output_tokens: int) -> dict:
        """Execute an already-authorized request assembled by the trusted backend."""
        meta = self.credentials.get_public(provider_id)
        provider = meta["provider"]
        if (provider not in ALLOWED_ENDPOINTS or meta["endpoint"] != ALLOWED_ENDPOINTS[provider]
                or not meta["enabled"]):
            raise ProviderAdapterError("POLICY_DENIED", "Provider chưa được phép thực thi")
        if (type(messages) is not list or not 1 <= len(messages) <= 32
                or any(type(item) is not dict or set(item) != {"role", "content"}
                       or item["role"] not in {"system", "user", "assistant"}
                       or type(item["content"]) is not str or len(item["content"]) > 32_768
                       for item in messages)
                or type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 2048):
            raise ProviderAdapterError("INVALID_REQUEST", "Payload provider không hợp lệ")
        self._limit(provider_id, meta["requests_per_minute"])
        secret = self.credentials.secret_for_backend(provider_id)
        request = {"model": meta["model"], "messages": messages, "stream": False,
                   "temperature": 0, "max_tokens": max_output_tokens}
        try:
            with self._client(meta["timeout_seconds"]) as client:
                response = client.post(meta["endpoint"] + "/v1/chat/completions", json=request,
                                       headers={"Authorization": "Bearer " + secret,
                                                "Content-Type": "application/json"})
            if response.status_code in {401, 403}:
                raise ProviderAdapterError("AUTH_FAILED", "API key bị provider từ chối")
            if response.status_code == 402:
                raise ProviderAdapterError("PROVIDER_BALANCE", "Tài khoản provider không đủ số dư")
            if response.status_code == 429:
                raise ProviderAdapterError("RATE_LIMITED", "Provider đang giới hạn request")
            if response.status_code >= 400:
                raise ProviderAdapterError("PROVIDER_ERROR", "Provider trả lỗi")
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            if type(content) is not str or not content.strip() or type(usage) is not dict:
                raise (ValueError("invalid provider response"))
            return {"provider_id": provider_id, "model": meta["model"], "content": content,
                    "usage": {"input_tokens": usage.get("prompt_tokens"),
                              "output_tokens": usage.get("completion_tokens")}}
        except ProviderAdapterError:
            raise
        except httpx.TimeoutException:
            raise ProviderAdapterError("OUTCOME_UNKNOWN", "Provider quá thời gian sau khi có thể đã gửi request") from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ProviderAdapterError("PROVIDER_ERROR", "Provider trả dữ liệu không hợp lệ") from None
