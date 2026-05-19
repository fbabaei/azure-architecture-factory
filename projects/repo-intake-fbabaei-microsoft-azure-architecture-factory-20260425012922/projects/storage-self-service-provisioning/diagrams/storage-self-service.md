# Storage Self-Service Provisioning Architecture

## Overview

This diagram captures the core workflow used by the storage self-service sample.

- The provisioning API accepts requests and validates payloads.
- A worker executes provisioning workflows and status transitions.
- Provisioned resources are applied to Azure storage targets.

## Notes

This architecture note is provided to align this sample with the repository lifecycle evidence model used by the readiness dashboard.
