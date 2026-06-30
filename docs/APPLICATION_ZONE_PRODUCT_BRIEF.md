# AAF Application Zone Product Brief (One Page)

## Executive Summary
AAF Application Zone is a curated catalog of production-ready AI application packs (App Packs) that users can deploy with guided configuration, built-in security controls, and day-2 operations. It shifts AAF from "architecture generation only" to "outcome delivery," starting with a flagship legal assistant pack based on CaseWright.

## Problem
Teams currently spend significant effort assembling architecture, security, observability, and deployment steps before they see business value from an AI application.

## Proposal
Introduce an Application Zone in AAF where users can:
- Select a prebuilt app (for example, CaseWright)
- Configure a small set of validated business inputs
- Deploy a governed instance with one guided flow
- Operate and upgrade instances through AAF lifecycle controls

## Why Now
- Demand is shifting from toolkit adoption to ready-to-use solution adoption.
- Security and compliance expectations require policy-first defaults.
- AAF already has orchestration and architecture assets that can be reused.

## MVP Scope
- Catalog page with curated App Packs and lifecycle badges
- App Pack contract (versioned metadata, inputs, deployment profile, operations policy)
- Guided deployment wizard with policy pre-checks
- Secure-by-default baseline: managed identity, Key Vault, least privilege RBAC, audit logs
- Built-in observability: health, traces, and starter evaluation workflow
- Day-2 operations: instance inventory, upgrades, rollback to last known good

## Out of Scope (MVP)
- Third-party marketplace publishing
- Cross-cloud deployment
- Arbitrary no-code workflow composer
- Fully automated multi-region active-active topology

## Pilot App Pack
CaseWright (legal case assistant):
- Input profile: jurisdiction, document source, identity mode, channel mode
- Built-in controls: sensitive content policies, retrieval safeguards, diagnostics defaults
- Validation: smoke tests + starter eval report + policy gate pass

## Success Metrics
- Median time to healthy deployed instance (< 60 minutes)
- First-attempt deployment success rate
- Policy violations prevented before deploy
- Time to first useful answer
- Upgrade success rate without rollback
- Pilot user satisfaction score

## Risks and Mitigations
- Pack drift: use strict semantic versioning, release checklist, and compatibility matrix
- Over-opinionated templates: enforce extension points and profile variants
- Cost sprawl: quotas, budget alerts, and environment defaults (dev/test/prod)
- Support load: define support tier, SLOs, and runbooks per App Pack

## 30/60/90 Rollout
- 0-30 days: schema, catalog UI, CaseWright pack skeleton, deployment wizard, policy gate
- 31-60 days: observability dashboards, eval starter, upgrade/rollback flow, pilot onboarding
- 61-90 days: GA hardening, second domain pack, operator runbook, contribution process

## Decision Ask
Approve MVP funding and staffing for an Application Zone pilot with CaseWright as the first App Pack and a 90-day delivery target.
