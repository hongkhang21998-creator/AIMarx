"""Module quản lý danh mục model công khai."""

_ALLOWED_INPUT_KEYS = frozenset({"id", "provider", "model", "enabled"})
# "ollama" là local duy nhất; mọi provider khác là cloud và đi qua policy_gate
# (mặc định chặn, tối đa chỉ CONSENT_REQUIRED). Chạy Qwen/DeepSeek/GLM trên máy thì
# khai provider "ollama", không phải tên hãng. Xem docs/NGHIEN_CUU_PROVIDER_2026-09.md.
_SUPPORTED_PROVIDERS = frozenset({"ollama", "deepseek", "glm", "qwen", "kimi"})
_ERROR_MESSAGE = "Cấu hình danh mục model không hợp lệ"


def list_public_models(
    entries: list[dict],
    *,
    enabled_only: bool = True,
) -> list[dict]:
    """Liệt kê danh mục model công khai từ cấu hình đầu vào."""
    if type(enabled_only) is not bool:
        raise ValueError(_ERROR_MESSAGE)
    if type(entries) is not list:
        raise ValueError(_ERROR_MESSAGE)

    seen_ids: set[str] = set()
    validated_entries: list[dict] = []

    for entry in entries:
        if type(entry) is not dict:
            raise ValueError(_ERROR_MESSAGE)
        if frozenset(entry.keys()) != _ALLOWED_INPUT_KEYS:
            raise ValueError(_ERROR_MESSAGE)

        raw_id = entry["id"]
        if type(raw_id) is not str:
            raise ValueError(_ERROR_MESSAGE)
        clean_id = raw_id.strip()
        if not clean_id:
            raise ValueError(_ERROR_MESSAGE)
        if clean_id in seen_ids:
            raise ValueError(_ERROR_MESSAGE)
        seen_ids.add(clean_id)

        provider = entry["provider"]
        if type(provider) is not str or provider not in _SUPPORTED_PROVIDERS:
            raise ValueError(_ERROR_MESSAGE)

        raw_model = entry["model"]
        if type(raw_model) is not str:
            raise ValueError(_ERROR_MESSAGE)
        clean_model = raw_model.strip()
        if not clean_model:
            raise ValueError(_ERROR_MESSAGE)

        enabled = entry["enabled"]
        if type(enabled) is not bool:
            raise ValueError(_ERROR_MESSAGE)

        destination = "local" if provider == "ollama" else "cloud"
        validated_entries.append({
            "id": clean_id,
            "provider": provider,
            "model": clean_model,
            "enabled": enabled,
            "data_destination": destination,
        })

    if enabled_only:
        return [item for item in validated_entries if item["enabled"]]
    return validated_entries