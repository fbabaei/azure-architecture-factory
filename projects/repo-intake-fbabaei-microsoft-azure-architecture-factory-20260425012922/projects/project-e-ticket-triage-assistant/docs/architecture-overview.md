# Architecture Overview

## Objective

Project E builds an AI-powered support ticket triage assistant that classifies tickets, recommends routing, and suggests resolution steps.

## Core Components

- Channel Intake: captures support requests from portal, email, and API channels.
- Triage API Layer: normalizes requests and coordinates orchestration.
- Classification and Routing Engine: predicts category, severity, and assignment queue.
- Knowledge Retrieval Layer: fetches runbooks, KB content, and policy references.
- Copilot Experience: provides suggested actions to support engineers.
- Telemetry and Governance: captures quality, latency, and audit signals.

## Azure Mapping

- Azure App Service or Container Apps for API and workflow execution.
- Azure OpenAI for classification and summarization tasks.
- Azure AI Search for retrieval-augmented knowledge lookup.
- Azure Storage for evidence and attachment storage.
- Application Insights + Log Analytics for observability.
