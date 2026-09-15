"""Consent-gated cloud gateway joining snapshot, grant, ledger and adapter."""

from __future__ import annotations

import os
import time
from pathlib import Path

from . import provider_grants, provider_ledger, provider_snapshot
from .provider_grants import Principal
from .provider_ledger import Ledger, Usage
from .provider_snapshot import SnapshotError, TrustedConfig


class ProviderGateway:
    ADAPTER_REVISION = "openai-compatible/1"

    def __init__(self, service, credentials, adapter, *, config_path=None, clock=None):
        self.service = service
        self.credentials = credentials
        self.adapter = adapter
        self.config_path = Path(config_path or os.getenv(
            "TLVB_PROVIDER_CONFIG", str(service.root / "provider-config.json")))
        self.clock = clock or (lambda: int(time.time() * 1000))

    def _config(self, provider_id: str, now_ms: int) -> TrustedConfig:
        self.adapter.require_cloud()
        selected = self.credentials.get_public(provider_id)
        if selected["provider"] == "ollama" or not selected["enabled"]:
            raise SnapshotError("POLICY_DENIED", "PROVIDER_DISABLED")
        self.credentials.secret_for_backend(provider_id)
        entries, _ = provider_ledger.load_config(self.config_path)
        matches = [entry for entry in entries if entry["provider"] == selected["provider"]
                   and entry["model"] == selected["model"] and entry["endpoint"] == selected["endpoint"]]
        if len(matches) != 1:
            raise provider_ledger.LedgerError("PRICING_UNVERIFIED", "NO_ENTRY")
        # Validate expiry before a preview is shown; reserve validates it again at dispatch.
        entry = provider_ledger._validate_rate_card_entry(matches[0], now_ms=now_ms)
        models = tuple({"id": row["id"], "provider": row["provider"], "model": row["model"],
                        "enabled": row["enabled"]} for row in self.credentials.list_public())
        return TrustedConfig(models=models, cloud_enabled=True,
            revisions={"adapter": self.ADAPTER_REVISION, "endpoint": selected["endpoint"],
                       "pricing": provider_ledger.pricing_revision(entry)},
            settings={"max_output_tokens": 1024, "temperature_milli": 0, "context_tokens": None})

    def prepare_chat(self, message: str, provider_id: str, classification: str) -> dict:
        if type(message) is not str or not message.strip() or len(message) > provider_snapshot.MAX_INSTRUCTION:
            raise ValueError("Nội dung yêu cầu không hợp lệ")
        now_ms = self.clock()
        config = self._config(provider_id, now_ms)
        request = {"operation": "draft", "model_id": provider_id, "sources": [],
                   "instruction": message.strip(), "facts": []}
        with self.service.db() as conn:
            view = provider_snapshot.prepare_snapshot(conn, request, config=config, now_ms=now_ms,
                                                      prompt_classification=classification)
        return {"snapshot_id": view.snapshot_id, "expires_at_ms": view.expires_at_ms,
                "provider_id": provider_id, "model": view.target["model"],
                "classification": view.effective_classification,
                "payload_sha256": view.payload_sha256, "payload_size": view.payload_size,
                "preview": view.payload()}

    def confirm_and_execute(self, snapshot_id: str, provider_id: str, *, principal_secret: bytes) -> dict:
        """Called only from the local CSRF-protected confirmation route."""
        now_ms = self.clock()
        config = self._config(provider_id, now_ms)
        ledger = Ledger(config_path=self.config_path)
        principal = Principal(principal_secret)
        with self.service.db() as conn:
            grant = provider_grants.issue_grant(conn, snapshot_id, principal=principal, now_ms=now_ms)
            authorization = provider_grants.authorize_dispatch(
                conn, snapshot_id, grant.token, principal=principal, config=config,
                now_ms=now_ms, ledger=ledger)
        payload = authorization.snapshot.payload()
        try:
            result = self.adapter.chat(provider_id, payload["messages"],
                                       max_output_tokens=payload["settings"]["max_output_tokens"])
            measured = result["usage"]
            if type(measured.get("input_tokens")) is not int or type(measured.get("output_tokens")) is not int:
                raise ValueError("usage missing")
            usage = Usage(measured["input_tokens"], measured["output_tokens"])
        except Exception:
            with self.service.db() as conn:
                provider_ledger.settle(conn, authorization.reservation.attempt_id,
                                       usage=None, outcome="failed", now_ms=self.clock())
            raise
        with self.service.db() as conn:
            ledger_state = provider_ledger.settle(conn, authorization.reservation.attempt_id,
                                                  usage=usage, outcome="completed", now_ms=self.clock())
        return {**result, "snapshot_id": snapshot_id, "ledger_state": ledger_state}
