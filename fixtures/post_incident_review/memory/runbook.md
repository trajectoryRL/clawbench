# Incident Response Runbook — Platform Team

## Severity Levels
- **P1**: Customer-facing service down. Response within 15 minutes. Incident commander required.
- **P2**: Degraded performance or partial outage. Response within 30 minutes.
- **P3**: Internal tooling down or non-critical service issue. Response within 2 hours.

## Incident Commander Responsibilities
1. Acknowledge incident in PagerDuty
2. Create incident channel or use #incidents
3. Coordinate diagnosis and fix
4. Communicate status to stakeholders every 30 minutes
5. Mark resolved when service is restored
6. Ensure PIR is filed within 48 hours

## Post-Incident Review Requirements
- Required for all P1 and P2 incidents
- Must be completed within 48 hours of resolution
- Use the PIR template at https://wiki.techcorp.com/pir-template
- Present findings to engineering leadership
- All action items must have owners and due dates

## Key Principles
- **Blameless culture**: Focus on systems and processes, not individuals
- **Timeline accuracy**: Use monitoring data and timestamps, not memory
- **Customer transparency**: Provide incident report to affected enterprise customers within 5 business days
- **Action tracking**: All PIR action items go into sprint backlog with priority >= medium
