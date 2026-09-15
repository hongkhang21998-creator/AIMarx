"""Provider metadata in SQLite and provider secrets in the OS credential vault."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_MAX_SECRET = 4096


class CredentialError(RuntimeError):
    """A stable public error which never contains credential backend details."""


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    provider: str
    model: str
    endpoint: str
    enabled: bool = False
    requests_per_minute: int = 10
    timeout_seconds: int = 45


DEFAULT_PROVIDERS = (
    ProviderDefinition("local-qwen", "ollama", "qwen3:0.6b", "http://127.0.0.1:11434", True, 60, 120),
    ProviderDefinition("deepseek-chat", "deepseek", "deepseek-chat", "https://api.deepseek.com", False, 10, 45),
    ProviderDefinition("openai-mini", "openai", "gpt-5-mini", "https://api.openai.com", False, 10, 45),
)


class KeyringBackend:
    def __init__(self):
        import keyring
        self._keyring = keyring

    def get(self, service: str, username: str) -> str | None:
        return self._keyring.get_password(service, username)

    def set(self, service: str, username: str, secret: str) -> None:
        self._keyring.set_password(service, username, secret)

    def delete(self, service: str, username: str) -> None:
        try:
            self._keyring.delete_password(service, username)
        except self._keyring.errors.PasswordDeleteError:
            pass


class CredentialStore:
    """Keeps only provider metadata and a one-way key fingerprint in SQLite."""

    def __init__(self, db, *, backend=None, definitions=DEFAULT_PROVIDERS, service_name="AIMarx/provider-key/v1"):
        self.db = db
        self.backend = backend or KeyringBackend()
        self.service_name = service_name
        self.definitions = tuple(definitions)
        self._validate_definitions()
        with db() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS providers (
                    id TEXT PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL,
                    endpoint TEXT NOT NULL, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                    requests_per_minute INTEGER NOT NULL, timeout_seconds INTEGER NOT NULL,
                    key_fingerprint TEXT, credential_updated_at TEXT);
            ''')
            for item in self.definitions:
                conn.execute('''INSERT INTO providers
                    (id,provider,model,endpoint,enabled,requests_per_minute,timeout_seconds)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING''',
                    (item.id, item.provider, item.model, item.endpoint, int(item.enabled),
                     item.requests_per_minute, item.timeout_seconds))

    def _validate_definitions(self):
        seen = set()
        for item in self.definitions:
            if (not isinstance(item, ProviderDefinition) or not _ID.fullmatch(item.id)
                    or item.id in seen or not item.provider or not item.model or not item.endpoint
                    or type(item.enabled) is not bool or type(item.requests_per_minute) is not int
                    or not 1 <= item.requests_per_minute <= 10_000
                    or type(item.timeout_seconds) is not int or not 1 <= item.timeout_seconds <= 300):
                raise ValueError("Cấu hình provider không hợp lệ")
            seen.add(item.id)

    @staticmethod
    def _fingerprint(secret: str) -> str:
        return "sha256:" + hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]

    def _row(self, provider_id: str):
        if type(provider_id) is not str or not _ID.fullmatch(provider_id):
            raise ValueError("Provider không hợp lệ")
        with self.db() as conn:
            row = conn.execute("SELECT * FROM providers WHERE id=?", (provider_id,)).fetchone()
        if row is None:
            raise ValueError("Provider không tồn tại")
        return dict(row)

    def list_public(self) -> list[dict]:
        with self.db() as conn:
            rows = conn.execute('''SELECT id,provider,model,endpoint,enabled,
                requests_per_minute,timeout_seconds,key_fingerprint FROM providers ORDER BY id''').fetchall()
        return [{**dict(row), "enabled": bool(row["enabled"]),
                 "has_credential": row["key_fingerprint"] is not None} for row in rows]

    def get_public(self, provider_id: str) -> dict:
        row = self._row(provider_id)
        return {key: row[key] for key in ("id", "provider", "model", "endpoint",
                "requests_per_minute", "timeout_seconds", "key_fingerprint")} | {
                    "enabled": bool(row["enabled"]), "has_credential": row["key_fingerprint"] is not None}

    def set_secret(self, provider_id: str, secret: str) -> dict:
        row = self._row(provider_id)
        if row["provider"] == "ollama":
            raise ValueError("Provider local không dùng API key")
        if type(secret) is not str or not 8 <= len(secret.strip()) <= _MAX_SECRET or "\x00" in secret:
            raise ValueError("API key không hợp lệ")
        value = secret.strip()
        try:
            self.backend.set(self.service_name, provider_id, value)
        except Exception:
            raise CredentialError("Không lưu được API key vào kho bí mật của hệ điều hành") from None
        fingerprint = self._fingerprint(value)
        try:
            with self.db() as conn:
                conn.execute("UPDATE providers SET key_fingerprint=?,credential_updated_at=CURRENT_TIMESTAMP WHERE id=?",
                             (fingerprint, provider_id))
        except Exception:
            try:
                self.backend.delete(self.service_name, provider_id)
            except Exception:
                pass
            raise CredentialError("Không cập nhật được metadata credential") from None
        return self.get_public(provider_id)

    def secret_for_backend(self, provider_id: str) -> str:
        row = self._row(provider_id)
        try:
            secret = self.backend.get(self.service_name, provider_id)
        except Exception:
            raise CredentialError("Không đọc được API key từ kho bí mật của hệ điều hành") from None
        if not secret or self._fingerprint(secret) != row["key_fingerprint"]:
            raise CredentialError("API key chưa có hoặc không khớp metadata")
        return secret

    def revoke(self, provider_id: str) -> dict:
        row = self._row(provider_id)
        if row["provider"] == "ollama":
            raise ValueError("Provider local không dùng API key")
        try:
            self.backend.delete(self.service_name, provider_id)
        except Exception:
            raise CredentialError("Không thu hồi được API key trong kho bí mật của hệ điều hành") from None
        with self.db() as conn:
            conn.execute("UPDATE providers SET key_fingerprint=NULL,credential_updated_at=NULL,enabled=0 WHERE id=?",
                         (provider_id,))
        return self.get_public(provider_id)

    def set_enabled(self, provider_id: str, enabled: bool) -> dict:
        row = self._row(provider_id)
        if type(enabled) is not bool:
            raise ValueError("Trạng thái provider không hợp lệ")
        if enabled and row["provider"] != "ollama" and not row["key_fingerprint"]:
            raise CredentialError("Phải thêm API key trước khi bật provider")
        with self.db() as conn:
            conn.execute("UPDATE providers SET enabled=? WHERE id=?", (int(enabled), provider_id))
        return self.get_public(provider_id)
