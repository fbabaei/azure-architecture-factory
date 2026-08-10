# AAPAAS success metrics

## MVP metrics

| Metric | Target |
| --- | --- |
| Time to register existing app instance | Less than 1 day |
| Time to healthy dev app-pack instance | Less than 1 day after Azure quota/capacity is available |
| Health-check coverage | 100% of registered instances have executable health checks |
| App-pack manifest coverage | 100% of catalog app packs have versioned manifests |
| Certification reporting | 100% of candidate packs have certification reports |

## Pilot metrics

| Metric | Target |
| --- | --- |
| Median time to healthy deployed instance | Less than 60 minutes after prerequisites are met |
| First-attempt deployment success rate | 80% or higher |
| Policy violations caught before deploy | 100% of known policy violations |
| Time to first useful answer | Less than 30 minutes after healthy deployment |
| Eval pass rate | 90% or higher for task success and groundedness |
| Safety pass rate | 100% for blocking safety cases |
| Upgrade success without rollback | 90% or higher |
| Pilot satisfaction | 4 out of 5 or higher |

## Operational metrics

| Metric | Target |
| --- | --- |
| API availability | 99.5% dev/test, 99.9% prod |
| P95 latency | Less than pack-specific SLO |
| Incident triage time | Less than 30 minutes |
| Cost anomaly detection | Same business day |
| Evaluation regression detection | Before promotion |
