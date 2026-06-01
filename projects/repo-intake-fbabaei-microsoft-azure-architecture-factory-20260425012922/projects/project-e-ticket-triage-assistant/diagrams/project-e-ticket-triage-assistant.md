# Project E Ticket Triage Assistant Diagram Notes

## Flow

1. Ticket enters via support channel.
2. API layer normalizes payload and forwards to triage workflow.
3. AI classification produces category and priority.
4. Retrieval layer gathers contextual runbooks.
5. Copilot suggestions are presented to support engineers.
6. Telemetry captures outcomes and feedback.
