# Incident History — Analytics Pipeline

## INC-2025-089 (September 12, 2025)
- **Cause**: Cache stampede during peak load. Multiple cache entries expired simultaneously, causing a thundering herd of database queries.
- **Duration**: 1 hour 45 minutes
- **Customer impact**: 23 enterprise customers affected, no SLA breach
- **Resolution**: Deployed jittered cache expiration (randomized TTL ±15%)
- **Action item**: Add circuit breaker to analytics pipeline → **Completed** (October 2025, task_412)
- **Root cause owner**: Tom Anderson

## INC-2025-112 (November 28, 2025)
- **Cause**: Cache invalidation timeout under high write volume. Write-heavy batch operations from a customer data import overwhelmed the invalidation queue.
- **Duration**: 3 hours 10 minutes
- **Customer impact**: 31 enterprise customers affected, 1 SLA breach (GlobalHealth, $45K penalty paid)
- **Resolution**: Emergency write throttling on batch import API
- **Action item**: Implement distributed cache lock for invalidation → **NOT completed** — deprioritized during Sprint 11 planning, then Sprint 12 planning. Still open as task_602.
- **Root cause owner**: Marcus Johnson

## Pattern Analysis
Cache-related outages are a recurring theme (3 incidents in 6 months if we count today's). The core problem — concurrent cache invalidation without proper synchronization — has been identified twice before. The distributed lock was promised after the November incident but was deprioritized each sprint due to competing feature work. This is a systemic risk management failure, not a one-off bug.
