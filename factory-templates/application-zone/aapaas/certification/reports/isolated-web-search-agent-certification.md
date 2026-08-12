# Isolated Web Search AgentPack certification

## Status

`certification-ready`

## Canonical source

`agent-application-factory/pocs/isolated-live-refresh-option-c`

## Certification decision

The Isolated Web Search agent is approved for inclusion in the governed AAPAAS catalog as a production-ready `AgentPack` based on Option C: Isolated Live-Refresh Snapshot.

Option C is the promoted source because it keeps the freshness benefits of live fetch while preserving answer-time isolation. The builder plane performs allowlisted HTTPS refresh, sanitizes and hashes documents, signs an immutable manifest, and atomically promotes the latest snapshot. The answer plane has no web egress and will not start unless the promoted snapshot signature, hashes, and version all verify.

## Evidence reviewed

- `README.md` documents Option C's production pattern: isolated live-refresh content plane plus no-egress answer plane.
- `ARCHITECTURE-GUIDE.md` documents the two independently deployed planes, signed artifact boundary, fail-closed verification, and operational extension points.
- `AGENTS.md` states the invariants for builder, answer plane, and shared signing key handling.
- `src/snapshot-builder/*` implements allowlisted fetch, redirect refusal, content-type/size checks, sanitization, hashing, signing, immutable version writing, and automatic promotion.
- `src/curated-research-agent/*` implements signature verification, content hash verification, deterministic local retrieval, and no-network answer-time behavior.
- `tests/*` validates both planes and the signed snapshot boundary.

## Local validation

```powershell
python -m pytest tests -q
```

Result:

```text
76 passed
```

## Strengths

- Strong two-plane design: content refresh plane has web egress but no model/tools; answer plane has model/tool surface but no web egress.
- Public-source freshness through automatic timer/queue refresh and atomic latest-snapshot promotion.
- Tamper evidence through per-document SHA-256 content hashes plus HMAC-signed manifest.
- Fail-closed answer-plane startup on missing pointer, missing version, bad signature, hash mismatch, version mismatch, missing file, duplicate id, or path escape.
- Builder refuses off-allowlist URLs, credentials, non-443 ports, IP literals, wildcards, local names, redirects, non-text content, and oversized responses.
- Agent exposes a single local retrieval tool with `tool_choice=required` and response storage disabled.
- Test suite validates allowlist, fetcher, sanitizer, signing, builder, store, corpus policy, retriever, and agent behavior.

## Production deployment requirements

Certification assumes the following deployment controls remain true:

1. Builder and answer plane use separate identities.
2. Signing key is managed outside source control, preferably in Key Vault.
3. Builder egress is restricted to approved HTTPS FQDNs at both application and network layers.
4. Answer plane has no live web egress.
5. Timer and queue refresh triggers run the same build-and-promote path.
6. Old snapshot versions are retained/pruned according to operations policy while the promoted version remains available.
