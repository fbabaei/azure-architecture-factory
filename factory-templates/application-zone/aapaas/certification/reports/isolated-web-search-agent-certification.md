# Isolated Web Search AgentPack certification

## Status

`candidate-agent-pack`

## Canonical source

`agent-application-factory/apps/isolated-web-search-agent`

## Certification decision

The Isolated Web Search agent is approved for inclusion in the governed AAPAAS catalog as a candidate `AgentPack`.

It is not yet marked `certification-ready` because the AAPAAS evidence snapshot does not include a deployed hosted runtime health result or a sample deployed invocation result.

## Evidence reviewed

- `README.md` describes the hosted-agent scaffold, provider modes, local run path, deployment notes, and required environment configuration.
- `ARCHITECTURE-GUIDE.md` documents the core security invariant: the component that reads the web has no privileged tools, and the privileged main agent never reads raw web pages.
- `AGENTS.md` states the project invariant and points to the JSON task/findings contract.
- `isolation_contracts.py` enforces task minimization, sensitive-content rejection, public HTTPS URL validation, prompt-injection detection, source provenance, budget limits, allowlist narrowing, and action gating.
- `tests/test_isolation_contracts.py` validates the core contract and guardrails.

## Local validation

```powershell
python -m pytest tests\test_isolation_contracts.py -q
```

Result:

```text
13 passed
```

## Strengths

- Clear separation between privileged reasoning and public-web reading.
- Sanitized subprocess/worker boundary for public web access.
- Strict JSON task/findings contract.
- SSRF-aware URL validation and public HTTPS enforcement.
- Configurable egress allowlist that can be narrowed but not widened by request payloads.
- Prompt-injection scanning on claims and citation snippets.
- Citation provenance requirements.
- Action gate defaults to requiring approval before privileged use of web-influenced findings.

## Remaining certification gaps

- Capture deployed Foundry hosted-agent runtime health evidence.
- Capture deployed sample invocation evidence with allowed public sources.
- Document owner for operator egress allowlist configuration.
- Decide the default provider mode for production deployments: WebIQ, Foundry Web Search, or constrained HTTP mode.

## Promotion criteria

Move from `candidate-agent-pack` to `certification-ready` only after:

1. A deployed hosted agent endpoint is available and healthy.
2. A sample invocation returns grounded findings with citations from allowed sources.
3. Runtime configuration proves that secrets are not passed to the isolated worker.
4. Operator-owned egress allowlists are documented.
