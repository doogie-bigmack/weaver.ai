# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for Weaver AI. ADRs document significant architectural decisions, their context, and their consequences.

## ADR Format

We use the following template for all ADRs:

```markdown
# ADR-XXX: [Title]

**Status**: [Proposed | Accepted | Deprecated | Superseded]
**Date**: YYYY-MM-DD
**Decision Makers**: [Names/Roles]
**Technical Story**: [Optional Jira/GitHub issue]

## Context

[Describe the forces at play, including technological, political, social, and project constraints]

## Decision

[Describe our response to these forces, i.e., what we decided to do]

## Consequences

### Positive
- [Benefit 1]
- [Benefit 2]

### Negative
- [Drawback 1]
- [Drawback 2]

### Neutral
- [Neutral impact 1]

## Alternatives Considered

### Alternative 1
- **Description**: [What it is]
- **Pros**: [Benefits]
- **Cons**: [Drawbacks]
- **Why not chosen**: [Reason]

## Implementation Notes

[Technical details, migration path, etc.]

## References

- [Link to related docs]
- [Link to discussion]
```

## Index of ADRs

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](./001-dual-api-design.md) | Dual API Design (Simple + BaseAgent) | Accepted | 2024-09-01 |
| [002](./002-redis-event-mesh.md) | Redis Event Mesh for Agent Communication | Accepted | 2024-09-05 |
| [003](./003-mcp-tool-protocol.md) | Model Context Protocol for Tools | Accepted | 2024-09-10 |
| [004](./004-capability-based-routing.md) | Capability-Based Agent Routing | Proposed | TBD |
| [005](./005-security-first-design.md) | Security-First Architecture | Proposed | TBD |
| [006](./006-signed-telemetry.md) | Cryptographic Signing for Audit Trails | Accepted | 2025-10-05 |

## Creating a New ADR

1. **Copy the template** from this README
2. **Number sequentially** (e.g., `007-my-decision.md`)
3. **Fill in all sections** with complete information
4. **Get review** from architecture team
5. **Commit** when status moves to "Accepted"
6. **Update index** in this README

## ADR Lifecycle

```
Proposed → (Review) → Accepted → (Time) → Deprecated → Superseded
                ↓
            Rejected
```

- **Proposed**: Under consideration, not yet implemented
- **Accepted**: Decision made, implementation may be in progress
- **Deprecated**: Still in use but discouraged, migration planned
- **Superseded**: Replaced by a newer ADR
- **Rejected**: Considered but not adopted

## Principles for ADRs

1. **Document the why, not just the what**: Explain context and forces
2. **Be honest about trade-offs**: No solution is perfect
3. **Keep it concise**: 1-2 pages maximum
4. **Link to evidence**: Reference benchmarks, discussions, RFCs
5. **Update when superseded**: Don't delete, mark as superseded

## Tools

- **View locally**: Any Markdown viewer
- **Export to PDF**: Use Pandoc or online converter
- **Version control**: All ADRs are tracked in git
- **Search**: `grep -r "keyword" docs/architecture/adr/`

## References

- [ADR GitHub Organization](https://adr.github.io/)
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [ADR Tools](https://github.com/npryce/adr-tools)
