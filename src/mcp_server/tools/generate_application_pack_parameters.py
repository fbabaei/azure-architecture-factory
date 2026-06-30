"""generate_application_pack_parameters — emit deploy-ready parameter files.

This tool converts validated App Pack inputs into environment-specific deployment
parameter artifacts that can be shipped with standalone bundles.

Outputs (per profile):
- deployment-parameters.<profile>.json (ARM/Bicep deploymentParameters format)
- <profile>.generated.bicepparam (Bicep params file)
- application-inputs.<profile>.json (full app inputs for runtime bootstrap)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKS_ROOT = _REPO_ROOT / "factory-templates" / "application-zone" / "packs"
_DEFAULT_OUTPUT_ROOT = _REPO_ROOT / "outputs" / "application-zone"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
_PROFILE_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def _safe_id(value: str, label: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        raise ValueError(f"{label} is required.")
    if not _ID_RE.fullmatch(candidate):
        raise ValueError(f"Invalid {label}: '{candidate}'")
    return candidate


def _safe_profile(profile: str) -> str:
    candidate = (profile or "").strip().lower()
    if not candidate:
        raise ValueError("profile is required.")
    if not _PROFILE_RE.fullmatch(candidate):
        raise ValueError(f"Invalid profile: '{candidate}'")
    return candidate


def _read_json(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
        return doc if isinstance(doc, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _parse_version_tuple(version: str) -> tuple:
    parts = []
    for token in (version or "").split("."):
        try:
            parts.append(int(token))
        except ValueError:
            parts.append(token)
    return tuple(parts)


def _resolve_manifest(pack_id: str, version: str) -> tuple[Path, dict] | tuple[None, None]:
    pack_dir = _PACKS_ROOT / pack_id
    if not pack_dir.exists():
        return None, None

    if version:
        manifest_path = pack_dir / version / "manifest.json"
        doc = _read_json(manifest_path)
        if doc is None:
            return None, None
        return manifest_path, doc

    candidates = []
    for manifest_path in pack_dir.glob("*/manifest.json"):
        doc = _read_json(manifest_path)
        if not doc:
            continue
        doc_version = doc.get("metadata", {}).get("version", "")
        candidates.append((doc_version, manifest_path, doc))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: _parse_version_tuple(item[0]), reverse=True)
    _, path, doc = candidates[0]
    return path, doc


def _validate_input_rule(rule: dict, value) -> str | None:
    field_type = rule.get("type")
    name = rule.get("name", "field")
    allowed_values = rule.get("allowedValues", [])

    if field_type == "string":
        if not isinstance(value, str) or not value.strip():
            return f"{name} must be a non-empty string"
    elif field_type == "enum":
        if value not in allowed_values:
            return f"{name} must be one of: {', '.join(allowed_values)}"
    elif field_type == "integer":
        if not isinstance(value, int):
            return f"{name} must be an integer"
    elif field_type == "boolean":
        if not isinstance(value, bool):
            return f"{name} must be a boolean"
    elif field_type == "object":
        if not isinstance(value, dict):
            return f"{name} must be an object"
        required_fields = rule.get("requiredFields", [])
        for field in required_fields:
            if field not in value:
                return f"{name}.{field} is required"

    return None


def _validate_pack_inputs(pack: dict, inputs: dict) -> list[str]:
    errors: list[str] = []
    required_rules = pack.get("inputs", {}).get("required", [])
    optional_rules = pack.get("inputs", {}).get("optional", [])

    for rule in required_rules:
        name = rule.get("name")
        if name not in inputs:
            errors.append(f"Missing required input: {name}")
            continue

        rule_error = _validate_input_rule(rule, inputs.get(name))
        if rule_error:
            errors.append(rule_error)

    optional_by_name = {rule.get("name"): rule for rule in optional_rules}
    required_by_name = {rule.get("name"): rule for rule in required_rules}

    for name, value in inputs.items():
        if name in required_by_name:
            continue
        if name in optional_by_name:
            rule_error = _validate_input_rule(optional_by_name[name], value)
            if rule_error:
                errors.append(rule_error)

    return errors


def _build_parameter_values(pack_id: str, profile: str, inputs: dict) -> dict[str, Any]:
    region = inputs.get("region", "eastus")
    document_source = inputs.get("documentSource", {}) if isinstance(inputs.get("documentSource"), dict) else {}

    # These keys align to current CaseWright infra/main.bicep parameters and remain
    # harmless defaults for other packs until pack-specific mappers are introduced.
    return {
        "baseName": inputs.get("baseName", pack_id),
        "environmentName": inputs.get("environmentName", profile),
        "location": region,
        "searchLocation": inputs.get("searchLocation", region),
        "apiImage": inputs.get("apiImage", "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"),
        "workerImage": inputs.get("workerImage", "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"),
        "graphTenantId": inputs.get("graphTenantId", document_source.get("tenantId", "")),
        "graphClientId": inputs.get("graphClientId", document_source.get("clientId", "")),
        "sharePointSyncSchedule": inputs.get("sharePointSyncSchedule", "0 0 */6 * * *"),
        "syncDefaultTenantId": inputs.get("syncDefaultTenantId", ""),
        "embeddingDimensions": int(inputs.get("embeddingDimensions", 3072)),
        "foundryAgentId": inputs.get("foundryAgentId", ""),
    }


def _render_bicepparam(profile: str, values: dict[str, Any]) -> str:
    lines = [
        "using '../main.bicep'",
        "",
    ]
    for key, value in values.items():
        if isinstance(value, bool):
            literal = "true" if value else "false"
        elif isinstance(value, int):
            literal = str(value)
        else:
            escaped = str(value).replace("'", "''")
            literal = f"'{escaped}'"
        lines.append(f"param {key} = {literal}")

    lines.append("")
    lines.append(f"// Generated by AAF Application Zone at {datetime.now().isoformat()}")
    return "\n".join(lines)


def generate_application_pack_parameters(
    pack_id: str,
    version: str = "",
    profile: str = "dev",
    inputs: dict[str, Any] | None = None,
    bundle_path: str = "",
) -> dict[str, Any]:
    """Generate environment-specific deployment parameter artifacts.

    Parameters
    ----------
    pack_id:
        App pack identifier (for example: ``casewright``).
    version:
        Optional version. If omitted, latest available version is used.
    profile:
        Environment profile (for example: ``dev``, ``test``, ``prod``).
    inputs:
        App Pack input values used to produce deployment parameters.
    bundle_path:
        Optional existing exported bundle path. When provided, files are
        written under ``<bundle_path>/deploy/parameters``.

    Returns
    -------
    dict
        Generation status and output file paths.
    """
    try:
        pack_id = _safe_id(pack_id, "pack_id")
        profile = _safe_profile(profile)
        version = (version or "").strip()
    except ValueError as exc:
        return {"error": str(exc)}

    if inputs is None:
        inputs = {}
    if not isinstance(inputs, dict):
        return {"error": "inputs must be an object."}

    manifest_path, manifest = _resolve_manifest(pack_id, version)
    if manifest_path is None or manifest is None:
        if version:
            return {"error": f"App pack not found: {pack_id}@{version}"}
        return {"error": f"No versions found for app pack: {pack_id}"}

    metadata = manifest.get("metadata", {})
    resolved_version = metadata.get("version", version or "unknown")

    validation_errors = _validate_pack_inputs(manifest, inputs)
    if validation_errors:
        return {
            "error": "Input validation failed.",
            "valid": False,
            "errors": validation_errors,
        }

    if bundle_path:
        target_root = Path(bundle_path).resolve() / "deploy" / "parameters"
    else:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        target_root = (_DEFAULT_OUTPUT_ROOT / f"{pack_id}-{resolved_version}-{stamp}" / "deploy" / "parameters").resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    values = _build_parameter_values(pack_id, profile, inputs)

    deployment_json = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {key: {"value": value} for key, value in values.items()},
    }

    json_path = target_root / f"deployment-parameters.{profile}.json"
    bicepparam_path = target_root / f"{profile}.generated.bicepparam"
    inputs_path = target_root / f"application-inputs.{profile}.json"

    json_path.write_text(json.dumps(deployment_json, indent=2), encoding="utf-8")
    bicepparam_path.write_text(_render_bicepparam(profile, values), encoding="utf-8")
    inputs_path.write_text(json.dumps(inputs, indent=2), encoding="utf-8")

    return {
        "status": "generated",
        "packId": pack_id,
        "version": resolved_version,
        "profile": profile,
        "manifestPath": str(manifest_path.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "outputDirectory": str(target_root),
        "files": {
            "deploymentParametersJson": str(json_path),
            "generatedBicepParam": str(bicepparam_path),
            "applicationInputs": str(inputs_path),
        },
    }
