# Success Criteria

## KPI Candidates
- Work-order API accepts, validates, and routes a new work order in under 500 ms end-to-end
- IoT telemetry is ingested, scored, and anomaly alerts are raised within 60 seconds of receipt
- Copilot AI recommendation endpoint returns a structured next-action response in under 2 seconds
- Approval workflow triggers escalation notification within 30 seconds of SLA breach threshold
- All secrets are sourced from Key Vault; zero hard-coded credentials in repository or manifests
- All services authenticate via Managed Identity; no service principal passwords in use
- Application Insights shows end-to-end distributed trace for every work-order API call
- Azure Policy compliance score is 100% for all provisioned resources
- Generated project passes the factory validation suite with no critical findings

## Measurement Approach
- Establish a baseline before implementation
- Track changes through test results, deployment validation, and user feedback
- Assign an owner for each acceptance criterion
