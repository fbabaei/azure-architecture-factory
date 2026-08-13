# AI Security Control Tower evals

This folder contains the Phase 2 offline eval gate for the candidate AI Security Control Tower AppPack and its Red/Blue/Green AgentPacks.

The evals validate the governance contract before runtime integrations exist:

- complete evidence envelopes
- approved lane classifications
- explicit approval requirements
- no autonomous destructive actions
- no automatic PR merge
- no production containment without named-human approval

## Run

```powershell
python factory-templates\application-zone\aapaas\evals\security-control-tower\run_security_evals.py
```

The command writes:

- `evidence/results.json`
- `evidence/scorecard.md`

## Promotion use

Passing this gate does not make the Security Control Tower certification-ready by itself. It proves the candidate governance contract is testable. Certification-ready promotion still requires runtime implementation, work-board persistence, tool integrations, and operational evidence.
