"""Tests nghiệm thu cho module model_catalog."""

import copy
import pytest
from tro_ly_van_ban.model_catalog import list_public_models

EXPECTED_ERROR = "Cấu hình danh mục model không hợp lệ"


def test_empty_catalog():
    assert list_public_models([]) == []
    assert list_public_models([], enabled_only=False) == []


def test_mixed_catalog_filtering_and_order_and_destinations():
    sample_entries = [
        {"id": " local-demo ", "provider": "ollama", "model": " synthetic-local ", "enabled": True},
        {"id": "ds-demo", "provider": "deepseek", "model": "synthetic-ds", "enabled": False},
        {"id": "glm-demo", "provider": "glm", "model": "synthetic-glm", "enabled": True},
    ]
    expected_default = [
        {"id": "local-demo", "provider": "ollama", "model": "synthetic-local", "enabled": True, "data_destination": "local"},
        {"id": "glm-demo", "provider": "glm", "model": "synthetic-glm", "enabled": True, "data_destination": "cloud"},
    ]
    result = list_public_models(sample_entries)
    assert result == expected_default
    for item in result:
        assert set(item.keys()) == {"id", "provider", "model", "enabled", "data_destination"}


def test_enabled_only_false_includes_disabled_entries():
    sample_entries = [
        {"id": " local-demo ", "provider": "ollama", "model": " synthetic-local ", "enabled": True},
        {"id": "ds-demo", "provider": "deepseek", "model": "synthetic-ds", "enabled": False},
        {"id": "glm-demo", "provider": "glm", "model": "synthetic-glm", "enabled": True},
    ]
    expected_all = [
        {"id": "local-demo", "provider": "ollama", "model": "synthetic-local", "enabled": True, "data_destination": "local"},
        {"id": "ds-demo", "provider": "deepseek", "model": "synthetic-ds", "enabled": False, "data_destination": "cloud"},
        {"id": "glm-demo", "provider": "glm", "model": "synthetic-glm", "enabled": True, "data_destination": "cloud"},
    ]
    result = list_public_models(sample_entries, enabled_only=False)
    assert result == expected_all


def test_strip_and_immutability():
    sample_entries = [
        {"id": "  model-1  ", "provider": "ollama", "model": "  llm-v1  ", "enabled": True},
    ]
    original_copy = copy.deepcopy(sample_entries)
    result = list_public_models(sample_entries)

    # Input is not modified
    assert sample_entries == original_copy
    assert sample_entries[0]["id"] == "  model-1  "
    assert sample_entries[0]["model"] == "  llm-v1  "

    # Stripped in result
    assert result[0]["id"] == "model-1"
    assert result[0]["model"] == "llm-v1"

    # Mutating output does not affect future calls or input
    result[0]["id"] = "tampered"
    result.append({"extra": True})
    assert sample_entries == original_copy

    second_call = list_public_models(sample_entries)
    assert second_call[0]["id"] == "model-1"
    assert len(second_call) == 1


@pytest.mark.parametrize(
    "entries",
    [
        # Same ID twice
        [
            {"id": "m1", "provider": "ollama", "model": "v1", "enabled": True},
            {"id": "m1", "provider": "deepseek", "model": "v2", "enabled": True},
        ],
        # Same ID after strip
        [
            {"id": "  m1  ", "provider": "ollama", "model": "v1", "enabled": True},
            {"id": "m1", "provider": "deepseek", "model": "v2", "enabled": True},
        ],
        # Duplicate with one disabled
        [
            {"id": "m1", "provider": "ollama", "model": "v1", "enabled": True},
            {"id": "m1", "provider": "deepseek", "model": "v2", "enabled": False},
        ],
        # Duplicate when both disabled
        [
            {"id": "m1", "provider": "ollama", "model": "v1", "enabled": False},
            {"id": "  m1 ", "provider": "glm", "model": "v2", "enabled": False},
        ],
    ],
)
def test_duplicate_id_rejected(entries):
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models(entries)


def test_case_sensitive_id():
    # ID is case-sensitive: 'M1' and 'm1' should both be accepted
    entries = [
        {"id": "M1", "provider": "ollama", "model": "v1", "enabled": True},
        {"id": "m1", "provider": "deepseek", "model": "v2", "enabled": True},
    ]
    result = list_public_models(entries)
    assert len(result) == 2
    assert [x["id"] for x in result] == ["M1", "m1"]


@pytest.mark.parametrize(
    "entry",
    [
        {"id": "", "provider": "ollama", "model": "m", "enabled": True},
        {"id": "   ", "provider": "ollama", "model": "m", "enabled": True},
        {"id": 123, "provider": "ollama", "model": "m", "enabled": True},
        {"id": None, "provider": "ollama", "model": "m", "enabled": True},
        {"id": "m", "provider": "ollama", "model": "", "enabled": True},
        {"id": "m", "provider": "ollama", "model": "   ", "enabled": True},
        {"id": "m", "provider": "ollama", "model": 456, "enabled": True},
        {"id": "m", "provider": "ollama", "model": None, "enabled": True},
    ],
)
def test_invalid_id_or_model_rejected(entry):
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models([entry])


@pytest.mark.parametrize(
    "invalid_provider",
    [
        "Ollama",
        "OLLAMA",
        "Deepseek",
        "DEEPSEEK",
        "Glm",
        "GLM",
        "openai",
        "claude",
        "gemini",
        "ollama ",
        "",
        123,
        None,
    ],
)
def test_invalid_or_wrong_casing_provider_rejected(invalid_provider):
    entry = {"id": "m1", "provider": invalid_provider, "model": "test", "enabled": True}
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models([entry])


@pytest.mark.parametrize("invalid_enabled", [0, 1, "true", "True", "false", None, [], {}, 1.0])
def test_non_bool_enabled_rejected(invalid_enabled):
    entry = {"id": "m1", "provider": "ollama", "model": "test", "enabled": invalid_enabled}
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models([entry])


@pytest.mark.parametrize("invalid_enabled_only", [0, 1, "true", "True", "false", None, [], {}, 1.0])
def test_non_bool_enabled_only_rejected(invalid_enabled_only):
    entries = [{"id": "m1", "provider": "ollama", "model": "test", "enabled": True}]
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models(entries, enabled_only=invalid_enabled_only)


@pytest.mark.parametrize(
    "invalid_entries",
    [
        None,
        "not-a-list",
        {"id": "m1", "provider": "ollama", "model": "test", "enabled": True},
        ("tuple",),
        123,
    ],
)
def test_invalid_entries_structure_rejected(invalid_entries):
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models(invalid_entries)


@pytest.mark.parametrize(
    "invalid_element",
    [
        None,
        "string-element",
        123,
        ["nested-list"],
        True,
    ],
)
def test_invalid_element_type_rejected(invalid_element):
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models([invalid_element])


@pytest.mark.parametrize(
    "entry",
    [
        # Missing keys
        {"id": "m1", "provider": "ollama", "model": "test"},
        {"id": "m1", "provider": "ollama", "enabled": True},
        {"id": "m1", "model": "test", "enabled": True},
        {"provider": "ollama", "model": "test", "enabled": True},
        # Extra keys
        {"id": "m1", "provider": "ollama", "model": "test", "enabled": True, "extra": "value"},
        {"id": "m1", "provider": "ollama", "model": "test", "enabled": True, "base_url": "http://localhost"},
    ],
)
def test_missing_or_extra_keys_rejected(entry):
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models([entry])


def test_invalid_disabled_entry_rejected_before_filtering():
    # Valid enabled entry + invalid disabled entry
    entries = [
        {"id": "valid-1", "provider": "ollama", "model": "m1", "enabled": True},
        {"id": "invalid-2", "provider": "unsupported", "model": "m2", "enabled": False},
    ]
    with pytest.raises(ValueError, match=f"^{EXPECTED_ERROR}$"):
        list_public_models(entries, enabled_only=True)


def test_api_key_sentinel_rejected_without_leak():
    sentinel = "SYNTHETIC_SECRET_DO_NOT_ECHO"
    entry = {
        "id": "m1",
        "provider": "ollama",
        "model": "test",
        "enabled": True,
        "api_key": sentinel,
    }
    with pytest.raises(ValueError) as exc_info:
        list_public_models([entry])

    msg = str(exc_info.value)
    assert msg == EXPECTED_ERROR
    assert sentinel not in msg
    assert "api_key" not in msg