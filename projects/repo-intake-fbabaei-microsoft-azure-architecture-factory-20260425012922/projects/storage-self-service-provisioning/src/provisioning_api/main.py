from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from shared_lib.config import Settings
from shared_lib.governance import validate_request_policy
from shared_lib.models import ProvisioningRequest, ProvisioningRequestCreate
from shared_lib.monitoring import create_event_publisher
from shared_lib.repository import create_request_repository


settings = Settings.from_env()
repository = create_request_repository(settings)
event_publisher = create_event_publisher(settings)
app = FastAPI(title="Storage Self-Service Provisioning API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/requests", response_model=ProvisioningRequest)
def create_request(payload: ProvisioningRequestCreate) -> ProvisioningRequest:
    request = ProvisioningRequest.new(payload)
    validate_request_policy(request, settings)
    created = repository.create(request)
    event_publisher.publish(created.request_id, "RequestSubmitted", "Provisioning request accepted")
    return created


@app.get("/requests", response_model=list[ProvisioningRequest])
def list_requests() -> list[ProvisioningRequest]:
    return repository.list_all()


@app.get("/requests/{request_id}", response_model=ProvisioningRequest)
def get_request(request_id: str) -> ProvisioningRequest:
    found = repository.get(request_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return found


@app.get("/monitoring", response_class=HTMLResponse)
def monitoring_page() -> str:
        requests = repository.list_all()
        status_totals: dict[str, int] = {}
        for item in requests:
                status_totals[item.status.value] = status_totals.get(item.status.value, 0) + 1

        summary_html = "".join(
                f"<li><strong>{status}</strong>: {count}</li>" for status, count in sorted(status_totals.items())
        )

        rows = []
        for item in sorted(requests, key=lambda r: r.updated_at, reverse=True):
                resources = item.resources or {}
                resources_display = ", ".join(f"{k}={v}" for k, v in resources.items()) if resources else "-"
                rows.append(
                        "<tr>"
                        f"<td>{item.request_id}</td>"
                        f"<td>{item.project}</td>"
                        f"<td>{item.team}</td>"
                        f"<td>{item.environment}</td>"
                        f"<td>{item.data_class}</td>"
                        f"<td>{item.status.value}</td>"
                        f"<td>{item.updated_at.isoformat()}</td>"
                        f"<td>{resources_display}</td>"
                        "</tr>"
                )

        table_rows = "".join(rows) or "<tr><td colspan='8'>No requests found.</td></tr>"

        return f"""
<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <title>Storage Self-Service Monitoring</title>
    <style>
        body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
        h1 {{ margin-bottom: 8px; }}
        .card {{ background: white; padding: 16px; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 16px; }}
        table {{ border-collapse: collapse; width: 100%; background: white; border: 1px solid #e2e8f0; }}
        th, td {{ border-bottom: 1px solid #e2e8f0; text-align: left; padding: 10px; font-size: 13px; }}
        th {{ background: #eff6ff; }}
        code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 6px; }}
    </style>
</head>
<body>
    <h1>Storage Self-Service Monitoring</h1>
    <p>Backend: <code>{settings.repository_backend}</code> | Event Publisher: <code>{settings.event_backend}</code></p>
    <div class=\"card\">
        <h3>Status Summary</h3>
        <ul>{summary_html or '<li>No status yet</li>'}</ul>
    </div>
    <table>
        <thead>
            <tr>
                <th>Request ID</th><th>Project</th><th>Team</th><th>Env</th><th>Data Class</th><th>Status</th><th>Updated</th><th>Resources</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
</body>
</html>
"""
