"""Preparation policy behavior, independent of grants, network and storage."""

import copy
import itertools
import socket

import pytest

from tro_ly_van_ban.policy_gate import PolicyDecision as Decision, evaluate_policy


def model(provider="deepseek", **changes):
    return {"id": "test-model", "provider": provider, "model": "synthetic-test", "enabled": True} | changes


def check(request=None, **changes):
    settings = {
        "models": [model()],
        "cloud_enabled": True,
        "prompt_classification": "synthetic",
        "source_classifications": ("public",),
    } | changes
    return evaluate_policy(
        {"operation": "extract", "model_id": "test-model"} if request is None else request,
        **settings,
    )


@pytest.mark.parametrize("provider", ["deepseek", "glm"])
@pytest.mark.parametrize("labels", list(itertools.product(["synthetic", "public"], repeat=2)))
def test_eligible_cloud_still_needs_consent(provider, labels):
    assert check(models=[model(provider)], prompt_classification=labels[0], source_classifications=(labels[1],)) is Decision.CONSENT_REQUIRED


def test_defaults_never_prepare_cloud():
    request = {"operation": "draft", "model_id": "test-model"}
    assert evaluate_policy(request, models=[model()]) is Decision.POLICY_DENIED
    assert evaluate_policy(request, models=[model()], cloud_enabled=True) is Decision.POLICY_DENIED
    assert evaluate_policy(request, models=[model()], prompt_classification="public") is Decision.POLICY_DENIED


@pytest.mark.parametrize("provider", ["deepseek", "glm"])
@pytest.mark.parametrize("label", ["internal", "restricted", "unknown"])
@pytest.mark.parametrize("position", ["prompt", "first", "last"])
def test_one_restricted_component_denies_entire_cloud_payload(provider, label, position):
    settings = {"models": [model(provider)]}
    if position == "prompt":
        settings["prompt_classification"] = label
    else:
        settings["source_classifications"] = (label, "public") if position == "first" else ("synthetic", label)
    assert check(**settings) is Decision.POLICY_DENIED


@pytest.mark.parametrize("label", ["synthetic", "public", "internal", "restricted", "unknown"])
def test_local_preparation_accepts_valid_labels_without_cloud_permission(label):
    assert check(models=[model("ollama")], cloud_enabled=False, prompt_classification=label, source_classifications=(label,)) is Decision.PREPARE_LOCAL


def test_new_draft_still_requires_prompt_classification():
    request = {"operation": "draft", "model_id": "test-model"}
    assert check(request, source_classifications=(), prompt_classification="unknown") is Decision.POLICY_DENIED
    assert check(request, source_classifications=(), prompt_classification="public") is Decision.CONSENT_REQUIRED
    assert check(source_classifications=()) is Decision.INVALID_REQUEST


@pytest.mark.parametrize("extra", ["approved", "classification", "cloud_enabled", "grant_token", "api_key", "base_url", "price", "client_id", "source_classifications", "prompt"])
def test_caller_cannot_supply_privileged_fields(extra):
    assert check({"operation": "draft", "model_id": "test-model", extra: "SYNTHETIC_SECRET_DO_NOT_ECHO"}) is Decision.INVALID_REQUEST


@pytest.mark.parametrize("invalid_request", [None, [], (), True, "text", {}, {"operation": "draft"}, {"model_id": "test-model"}])
def test_invalid_request_structure(invalid_request):
    assert evaluate_policy(invalid_request, models=[model()]) is Decision.INVALID_REQUEST


@pytest.mark.parametrize("field,value", [
    ("operation", "approve"), ("operation", "Draft"), ("operation", " draft "),
    ("operation", []), ("operation", None), ("operation", True),
    ("model_id", ""), ("model_id", " \n"), ("model_id", 1),
    ("model_id", None), ("model_id", {}), ("model_id", "x" * 129),
])
def test_invalid_request_values(field, value):
    assert check({"operation": "draft", "model_id": "test-model"} | {field: value}) is Decision.INVALID_REQUEST


@pytest.mark.parametrize("value", [0, 1, "true", None, [], {}])
def test_cloud_enabled_is_strict_bool(value):
    assert check(cloud_enabled=value) is Decision.INVALID_REQUEST


@pytest.mark.parametrize("value", [None, 1, True, [], {}, "PUBLIC", " public ", "", "secret"])
def test_invalid_labels_not_silently_normalized(value):
    assert check(prompt_classification=value) is Decision.INVALID_REQUEST
    assert check(source_classifications=(value,)) is Decision.INVALID_REQUEST


@pytest.mark.parametrize("value", [None, [], ["public"], "public", {"public"}, 1, True])
def test_source_labels_require_tuple(value):
    assert check(source_classifications=value) is Decision.INVALID_REQUEST


def test_source_limit_and_model_id_boundaries():
    assert check(source_classifications=("public",) * 20) is Decision.CONSENT_REQUIRED
    assert check(source_classifications=("public",) * 21) is Decision.INVALID_REQUEST
    assert check({"operation": "draft", "model_id": "x" * 128}, models=[model(id="x" * 128)]) is Decision.CONSENT_REQUIRED


@pytest.mark.parametrize("models", [[], [model(enabled=False)], [model(id="other")]])
def test_unavailable_model_denied(models):
    assert check(models=models) is Decision.POLICY_DENIED


@pytest.mark.parametrize("models", [None, {}, (), [None], [model(enabled=1)], [model(provider="unknown-provider")], [model(api_key="secret")], [model(), model(id=" test-model ", enabled=False)]])
def test_invalid_catalogue(models):
    assert check(models=models) is Decision.INVALID_REQUEST


def test_unrelated_disabled_malformed_model_cannot_be_hidden():
    assert check(models=[model(), model(id="other", enabled=False, provider="invalid")]) is Decision.INVALID_REQUEST


def test_catalogue_size_boundary():
    entries = [model(id=str(i)) for i in range(100)]
    request = {"operation": "draft", "model_id": "0"}
    assert check(request, models=entries) is Decision.CONSENT_REQUIRED
    assert check(request, models=entries + [model()]) is Decision.INVALID_REQUEST


def test_id_matching_is_trimmed_and_case_sensitive():
    assert check(models=[model(id=" test-model ")]) is Decision.CONSENT_REQUIRED
    assert check({"operation": "draft", "model_id": " test-model "}) is Decision.CONSENT_REQUIRED
    assert check({"operation": "draft", "model_id": "TEST-MODEL"}) is Decision.POLICY_DENIED


def test_invalid_data_rejected_even_when_local_or_disabled():
    assert check(models=[model("ollama")], source_classifications=("PUBLIC",)) is Decision.INVALID_REQUEST
    assert check(cloud_enabled=False, prompt_classification=[]) is Decision.INVALID_REQUEST


def test_no_mutation_or_decision_cache():
    entries = [model()]
    request = {"operation": "draft", "model_id": "test-model"}
    before = copy.deepcopy((entries, request))
    assert check(request, models=entries) is Decision.CONSENT_REQUIRED
    assert (entries, request) == before
    entries[0]["enabled"] = False
    assert check(request, models=entries) is Decision.POLICY_DENIED


@pytest.mark.parametrize("decision", list(Decision))
def test_decisions_cannot_be_used_as_boolean_authorization(decision):
    with pytest.raises(TypeError, match="So sánh rõ PolicyDecision"):
        bool(decision)


def test_pure_evaluation_does_not_open_files_network_or_log(monkeypatch, caplog, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("PolicyGate attempted I/O")

    with monkeypatch.context() as guard:
        guard.setattr("builtins.open", forbidden)
        guard.setattr(socket, "socket", forbidden)
        for provider in ("ollama", "deepseek", "glm"):
            check(models=[model(provider)])
        result = check({"operation": "draft", "model_id": "SYNTHETIC_SECRET_DO_NOT_ECHO"})
    assert result is Decision.POLICY_DENIED
    assert "SYNTHETIC_SECRET_DO_NOT_ECHO" not in repr(result)
    assert caplog.text == ""
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
