"""Azure Developer CLI (azd) emitter.

Turns a generated project's ``project-manifest.json`` into the two artifacts
``azd`` needs to provision + deploy a Bicep-backed project:

  * ``azure.yaml``               — service map (host/language/docker) + infra ref
  * ``infra/main.parameters.json`` — ARM-style params wired to azd env vars

Design intent (see the factory discussion):
  * Bicep stays the *source of truth*. This emitter produces a thin azd
    *adapter* derived from the same manifest the IaC agent already consumes.
  * It is COMPLEMENTARY to an :class:`~iac_agents.base.IacAgent` (it does not
    implement that toolchain-exclusive Protocol) — wire it to run alongside the
    Bicep agent in the Architecture phase, not as a replacement.
  * No new runtime dependencies: YAML/JSON are built directly (matching the
    string-building style of ``bicep_agent.py``).

ALIGNMENT CAVEAT
----------------
The Bicep parameter *names* (e.g. ``apiImage``, ``embeddingDimensions``) are
owned by ``infra/main.bicep``. This emitter derives them by convention from the
manifest; the one real drift risk is a mismatch between the names emitted here
and the params declared in ``main.bicep``. Keep both generated from the same
parameter model, and gate them with a consistency check (every ``main.bicep``
param must have an entry here, and vice-versa).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------- #
# Service-type -> azd host/language mapping                                    #
# --------------------------------------------------------------------------- #
_HOST_BY_TYPE: dict[str, str] = {
    "container-app": "containerapp",
    "containerapp": "containerapp",
    "function-app": "function",
    "functionapp": "function",
    "app-service": "appservice",
    "appservice": "appservice",
}

_LANGUAGE_BY_TYPE: dict[str, str] = {
    "container-app": "docker",
    "function-app": "python",
    "app-service": "python",
}


def _norm_type(service_type: str) -> str:
    return (service_type or "").strip().lower().replace("_", "-")


def _env_token(service_name: str) -> str:
    """``casewright-api`` -> ``SERVICE_CASEWRIGHT_API_IMAGE_NAME`` token stem."""
    return re.sub(r"[^A-Z0-9]+", "_", service_name.upper()).strip("_")


def _role_suffix(service_name: str, project_name: str) -> str:
    """Derive a short role (``api``/``worker``) from ``<project>-<role>``."""
    stem = service_name
    prefix = f"{project_name}-"
    if stem.startswith(prefix):
        stem = stem[len(prefix):]
    return re.sub(r"[^a-z0-9]+", "", stem.lower()) or "app"


def normalize_manifest(manifest: dict[str, Any], slug: str | None = None) -> dict[str, Any]:
    """Accept both the rich (Casewright-style) and the flat runtime manifest.

    The runtime manifest emitted by ``local_brd_runner`` is flat (``project``,
    ``title``, ``iac_files`` …) and carries no ``services``/``structure``. We
    fill sensible defaults so the same emitter handles both shapes. When no
    services are modelled we infer a single external container-app, which is the
    common starter case.
    """
    name = manifest.get("name") or manifest.get("project") or slug or "app"
    structure = dict(manifest.get("structure") or {})
    structure.setdefault("source", f"src/{name}")
    structure.setdefault("infra", "infra")

    services = list(manifest.get("services") or [])
    if not services:
        services = [{"name": f"{name}-api", "type": "container-app", "ingress": "external"}]

    return {
        **manifest,
        "name": name,
        "structure": structure,
        "services": services,
    }


# --------------------------------------------------------------------------- #
# Emit context / result                                                       #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AzdEmitContext:
    """Inputs for the azd emitter.

    ``slug`` lets the runtime (flat) manifest supply the project name used for
    azd env-var tokens; when omitted it falls back to the manifest's
    ``name``/``project`` field.
    """

    project_root: Path
    manifest: dict[str, Any]
    slug: str | None = None


@dataclass
class AzdEmitResult:
    files_written: list[str] = field(default_factory=list)
    deploy_bullets: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# azure.yaml                                                                   #
# --------------------------------------------------------------------------- #
def build_azure_yaml(manifest: dict[str, Any]) -> str:
    """Render ``azure.yaml`` from the manifest's ``services[]``."""
    name = manifest["name"]
    version = manifest.get("version", "1.0.0")
    source = manifest.get("structure", {}).get("source", f"src/{name}")
    infra_dir = manifest.get("structure", {}).get("infra", "infra")
    # Docker build context = repo root of the package's top dir (e.g. "src").
    src_top = source.split("/", 1)[0] if "/" in source else source

    lines: list[str] = [
        "# Generated by aaf azd_emitter — derived from project-manifest.json.",
        "# Bicep (infra/main.bicep) is the source of truth; this is the azd adapter.",
        f"name: {name}",
        "metadata:",
        f"  template: {name}@{version}",
        "infra:",
        "  provider: bicep",
        f"  path: {infra_dir}",
        "  module: main",
        "services:",
    ]

    for svc in manifest.get("services", []):
        svc_name = svc["name"]
        stype = _norm_type(svc["type"])
        host = _HOST_BY_TYPE.get(stype, "containerapp")
        language = svc.get("language") or _LANGUAGE_BY_TYPE.get(stype, "python")

        # Project path: explicit override wins; else convention by host.
        if svc.get("project"):
            project = svc["project"]
        elif host == "function":
            project = f"{source}/functions/{_role_suffix(svc_name, name)}"
        else:
            project = src_top

        lines.append(f"  {svc_name}:")
        lines.append(f"    project: {project}")
        lines.append(f"    language: {language}")
        lines.append(f"    host: {host}")
        if language == "docker":
            lines.append("    docker:")
            lines.append(f"      path: {svc.get('dockerfile', 'Dockerfile')}")
            lines.append(f"      context: {svc.get('dockerContext', '.')}")

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# infra/main.parameters.json                                                  #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BicepParam:
    """One ``main.bicep`` parameter mapped to an azd-substitutable value."""

    name: str
    value: str  # e.g. "${AZURE_ENV_NAME=dev}" or "${AZURE_LOCATION}"


def derive_params_from_manifest(manifest: dict[str, Any]) -> list[BicepParam]:
    """Best-effort param set mirroring ``main.bicep`` (see ALIGNMENT CAVEAT).

    Base params are always emitted; archetype-specific params are added only
    when the manifest shows the matching feature (embedding model, SharePoint
    sync, etc.).
    """
    name = manifest["name"]
    params: list[BicepParam] = [
        BicepParam("baseName", f"${{AZURE_BASE_NAME={name}}}"),
        BicepParam("environmentName", "${AZURE_ENV_NAME=dev}"),
        BicepParam("location", "${AZURE_LOCATION}"),
    ]

    # One image param per container service: <role>Image -> SERVICE_<NAME>_IMAGE_NAME.
    placeholder = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
    for svc in manifest.get("services", []):
        if _norm_type(svc["type"]) not in ("container-app", "containerapp"):
            continue
        role = _role_suffix(svc["name"], name)
        token = _env_token(svc["name"])
        params.append(
            BicepParam(f"{role}Image", f"${{SERVICE_{token}_IMAGE_NAME={placeholder}}}")
        )

    # SharePoint / Microsoft Graph signals.
    sb_queue = manifest.get("data", {}).get("serviceBus", {}).get("queue", "")
    has_sharepoint = "sharepoint" in sb_queue.lower() or any(
        "sharepoint" in fn.lower()
        for agent in manifest.get("agents", [])
        for fn in agent.get("functions", [])
    )
    if has_sharepoint:
        params += [
            BicepParam("graphTenantId", "${GRAPH_TENANT_ID=}"),
            BicepParam("graphClientId", "${GRAPH_CLIENT_ID=}"),
            BicepParam("sharePointSyncSchedule", "${SHAREPOINT_SYNC_SCHEDULE=0 0 */6 * * *}"),
            BicepParam("syncDefaultTenantId", "${SYNC_DEFAULT_TENANT_ID=}"),
        ]

    # Embedding dimensions must match the retrieval index.
    dims = manifest.get("models", {}).get("embedding", {}).get("dimensions")
    if dims is not None:
        params.append(
            BicepParam("embeddingDimensions", f"${{AZURE_OPENAI_EMBEDDING_DIMENSIONS={dims}}}")
        )

    return params


def build_main_parameters(params: list[BicepParam]) -> str:
    """Render an ARM-style ``main.parameters.json`` with azd substitutions."""
    doc = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {p.name: {"value": p.value} for p in params},
    }
    return json.dumps(doc, indent=2) + "\n"


# Matches `param <name> <type> = <default>` / `param <name> <type>` at line start.
_BICEP_PARAM_RE = re.compile(
    r"^\s*param\s+(?P<name>\w+)\s+(?P<type>\w+)\s*(?:=\s*(?P<default>.+?))?\s*$",
    re.MULTILINE,
)

# Curated azd env-var names for a few well-known params whose generated token
# would otherwise diverge from the hand-authored convention.
_KNOWN_ENV_BY_PARAM: dict[str, str] = {
    "sharepointsyncschedule": "SHAREPOINT_SYNC_SCHEDULE",
    "embeddingdimensions": "AZURE_OPENAI_EMBEDDING_DIMENSIONS",
}


def _azd_value_for(name: str, default: str | None, slug: str) -> str:
    """Map a Bicep param name -> azd ``${ENV=default}`` substitution.

    Well-known names get canonical azd env vars (location, env, base name,
    image refs); everything else falls back to ``${<UPPER_SNAKE>=<default>}``
    using the Bicep default (string literals unquoted) as the azd default.
    """
    lower = name.lower()
    clean_default = ""
    if default is not None:
        d = default.strip()
        if (d.startswith("'") and d.endswith("'")) or (d.startswith('"') and d.endswith('"')):
            clean_default = d[1:-1]
        elif d.startswith("resourceGroup()"):
            clean_default = ""  # runtime-resolved; let azd supply location
        else:
            clean_default = d  # numeric / bool / expression

    if lower in ("location",):
        return "${AZURE_LOCATION}"
    if lower in ("environment", "environmentname"):
        return "${AZURE_ENV_NAME=dev}"
    if lower in ("workloadname", "basename"):
        return f"${{AZURE_BASE_NAME={clean_default or slug}}}"
    if lower.endswith("image"):
        role = re.sub(r"image$", "", lower) or "api"
        token = re.sub(r"[^A-Z0-9]+", "_", f"{slug}-{role}".upper()).strip("_")
        placeholder = clean_default or "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
        return f"${{SERVICE_{token}_IMAGE_NAME={placeholder}}}"

    # Curated env-var names for well-known params (preserve hand-authored convention).
    known = _KNOWN_ENV_BY_PARAM.get(lower)
    env_token = known or re.sub(r"[^A-Z0-9]+", "_", re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()).strip("_")
    return f"${{{env_token}={clean_default}}}"


def params_from_bicep(bicep_text: str, slug: str) -> list[BicepParam]:
    """Derive azd parameters by parsing the ACTUAL ``main.bicep``.

    This is the drift-proof path: the parameters.json always mirrors exactly the
    params the emitted Bicep declares, regardless of archetype.
    """
    out: list[BicepParam] = []
    for m in _BICEP_PARAM_RE.finditer(bicep_text):
        name = m.group("name")
        default = m.group("default")
        out.append(BicepParam(name, _azd_value_for(name, default, slug)))
    return out


# --------------------------------------------------------------------------- #
# Emitter facade                                                              #
# --------------------------------------------------------------------------- #
class AzdEmitter:
    """Writes ``azure.yaml`` + ``infra/main.parameters.json`` for a project."""

    name = "azd"
    display_name = "Azure Developer CLI"

    def emit(self, ctx: AzdEmitContext) -> AzdEmitResult:
        manifest = normalize_manifest(ctx.manifest, ctx.slug)
        slug = manifest["name"]
        result = AzdEmitResult()

        azure_yaml = ctx.project_root / "azure.yaml"
        azure_yaml.write_text(build_azure_yaml(manifest), encoding="utf-8")
        result.files_written.append(str(azure_yaml))

        infra_dir = manifest.get("structure", {}).get("infra", "infra")
        # Drift-proof path: if the Bicep already exists, parse its params so the
        # parameters.json mirrors exactly what main.bicep declares. Otherwise
        # fall back to deriving params from the (rich) manifest.
        bicep_path = ctx.project_root / infra_dir / "main.bicep"
        if bicep_path.is_file():
            params = params_from_bicep(bicep_path.read_text(encoding="utf-8"), slug)
        else:
            params = derive_params_from_manifest(manifest)

        params_path = ctx.project_root / infra_dir / "main.parameters.json"
        params_path.parent.mkdir(parents=True, exist_ok=True)
        params_path.write_text(build_main_parameters(params), encoding="utf-8")
        result.files_written.append(str(params_path))

        result.deploy_bullets = [
            "azd auth login",
            "azd env new <env-name>",
            "azd up   # provision (Bicep) + build/push images + deploy services",
        ]
        return result


AGENT = AzdEmitter()


# --------------------------------------------------------------------------- #
# Manual smoke test: python -m iac_agents.azd_emitter <project-dir>           #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":  # pragma: no cover
    import sys

    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    data = json.loads((root / "project-manifest.json").read_text(encoding="utf-8"))
    print("=== azure.yaml ===")
    print(build_azure_yaml(data))
    print("=== infra/main.parameters.json ===")
    print(build_main_parameters(derive_params_from_manifest(data)))
