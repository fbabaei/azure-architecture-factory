telemetry_enabled = False

def init_otel(service_name: str = "aaf-portal", service_version: str = "1.0.0") -> bool:
    """
    Initialize OpenTelemetry with Azure Monitor exporter.

    No-op (returns False) when:
      - opentelemetry / azure.monitor packages are not installed
      - APPLICATIONINSIGHTS_CONNECTION_STRING env var is not set
      - OTEL_SDK_DISABLED=true

    Returns True if telemetry was successfully initialized.
    """
    global telemetry_enabled
    import os

    if os.environ.get("OTEL_SDK_DISABLED", "").lower() in ("true", "1", "yes"):
        return False

    conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not conn_str:
        return False

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor  # type: ignore
    except ImportError:
        # Telemetry deps not installed — silent no-op so stdlib-only
        # deployments continue working.
        return False

    # The Azure Monitor exporter uses the Azure SDK's HttpLoggingPolicy which
    # dumps every telemetry-export HTTP request/response at INFO level. Left
    # alone, this fills Log Analytics with exporter-loop noise and drowns
    # real portal logs. Silence those loggers before initializing.
    import logging
    for _noisy in (
        "azure",
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.monitor.opentelemetry.exporter",
    ):
        logging.getLogger(_noisy).setLevel(logging.WARNING)

    try:
        configure_azure_monitor(
            connection_string=conn_str,
            resource_attributes={
                "service.name": service_name,
                "service.version": service_version,
                "service.namespace": "aaf",
            },
            logger_name="aaf-portal",
        )
        telemetry_enabled = True
        return True
    except Exception as exc:  # pragma: no cover - defensive
        import sys
        print(f"[telemetry] init failed: {exc}", file=sys.stderr)
        return False


def get_tracer(name: str = "aaf-portal"):
    """Return an OTel tracer, or a no-op tracer if OTel isn't initialized."""
    try:
        from opentelemetry import trace  # type: ignore
        return trace.get_tracer(name)
    except ImportError:
        return _NoopTracer()


class _NoopSpan:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def set_attribute(self, *args, **kwargs):
        pass

    def set_status(self, *args, **kwargs):
        pass

    def record_exception(self, *args, **kwargs):
        pass


class _NoopTracer:
    def start_as_current_span(self, *args, **kwargs):
        return _NoopSpan()
