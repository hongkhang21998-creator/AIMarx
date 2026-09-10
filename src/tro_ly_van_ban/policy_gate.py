"""Pure preparation policy; no decision here authorizes provider execution.

Only ``request`` comes from a caller. The backend must supply the catalogue,
cloud setting and classifications from trusted local configuration/records.
Never expose these keyword arguments directly as MCP or HTTP input fields.
"""

from enum import Enum

from .model_catalog import list_public_models


class PolicyDecision(Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    POLICY_DENIED = "POLICY_DENIED"
    PREPARE_LOCAL = "PREPARE_LOCAL"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"

    def __bool__(self):
        raise TypeError("So sánh rõ PolicyDecision; đây không phải quyền thực thi")


_REQUEST_KEYS = frozenset({"operation", "model_id"})
_OPERATIONS = frozenset({"extract", "draft"})
_CLASSIFICATIONS = frozenset({"synthetic", "public", "internal", "restricted", "unknown"})
_CLOUD_CLASSIFICATIONS = frozenset({"synthetic", "public"})


def evaluate_policy(
    request: dict,
    *,
    models: list[dict],
    cloud_enabled: bool = False,
    prompt_classification: str = "unknown",
    source_classifications: tuple[str, ...] = (),
) -> PolicyDecision:
    """Check eligibility to prepare a request under PSC-01.

    Source labels correspond to all selected blocks (max 20). The prompt label
    covers instructions and every other payload component, including new draft
    facts, templates and schema. Missing labels must be supplied as ``unknown``;
    this function cannot verify provenance or that the backend covered all data.

    INVALID_REQUEST takes precedence over policy decisions. A disabled/unknown
    model is denied. Cloud needs an explicit enabled setting and every label
    must be public/synthetic, but the result is still only CONSENT_REQUIRED.
    Local eligibility does not verify its endpoint, grant access to documents,
    reserve funds, validate a snapshot, or permit saving/approving a draft.
    """
    if type(request) is not dict or frozenset(request) != _REQUEST_KEYS:
        return PolicyDecision.INVALID_REQUEST
    operation = request["operation"]
    model_id = request["model_id"]
    if type(operation) is not str or operation not in _OPERATIONS:
        return PolicyDecision.INVALID_REQUEST
    if type(model_id) is not str or not model_id.strip() or len(model_id) > 128:
        return PolicyDecision.INVALID_REQUEST
    if type(cloud_enabled) is not bool:
        return PolicyDecision.INVALID_REQUEST
    if type(prompt_classification) is not str or prompt_classification not in _CLASSIFICATIONS:
        return PolicyDecision.INVALID_REQUEST
    if type(source_classifications) is not tuple or len(source_classifications) > 20:
        return PolicyDecision.INVALID_REQUEST
    if any(type(label) is not str or label not in _CLASSIFICATIONS for label in source_classifications):
        return PolicyDecision.INVALID_REQUEST
    if operation == "extract" and not source_classifications:
        return PolicyDecision.INVALID_REQUEST
    if type(models) is not list or len(models) > 100:
        return PolicyDecision.INVALID_REQUEST
    try:
        # Validate disabled and unrelated entries too; never filter away errors.
        catalogue = list_public_models(models, enabled_only=False)
    except ValueError:
        return PolicyDecision.INVALID_REQUEST

    selected = next((model for model in catalogue if model["id"] == model_id.strip()), None)
    if selected is None or not selected["enabled"]:
        return PolicyDecision.POLICY_DENIED
    if selected["provider"] == "ollama":
        return PolicyDecision.PREPARE_LOCAL
    if not cloud_enabled:
        return PolicyDecision.POLICY_DENIED
    if any(label not in _CLOUD_CLASSIFICATIONS for label in (prompt_classification, *source_classifications)):
        return PolicyDecision.POLICY_DENIED
    return PolicyDecision.CONSENT_REQUIRED
