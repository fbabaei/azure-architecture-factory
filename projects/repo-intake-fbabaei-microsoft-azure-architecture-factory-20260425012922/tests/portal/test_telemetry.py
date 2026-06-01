"""Tests for scripts/telemetry.py — OpenTelemetry init + no-op fallbacks.

Covers:
- init_otel returns False when APPLICATIONINSIGHTS_CONNECTION_STRING is unset
- init_otel returns False when OTEL_SDK_DISABLED=true
- init_otel returns False gracefully when azure.monitor is not importable
- get_tracer always returns a usable object (real or _NoopTracer)
- _NoopSpan behaves as a context manager and accepts attribute / exception
  / status calls without raising
"""
from __future__ import annotations

import importlib
import sys
from unittest import mock

import pytest

import telemetry  # noqa: E402  (path set by conftest)


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    """Ensure each test starts with telemetry_enabled=False and a clean env."""
    monkeypatch.setattr(telemetry, "telemetry_enabled", False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    yield


def test_init_otel_noop_without_connection_string():
    assert telemetry.init_otel() is False
    assert telemetry.telemetry_enabled is False


def test_init_otel_noop_when_sdk_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=00000000-0000-0000-0000-000000000000",
    )
    assert telemetry.init_otel() is False


@pytest.mark.parametrize("value", ["true", "True", "1", "yes", "YES"])
def test_init_otel_respects_disabled_variants(monkeypatch, value):
    monkeypatch.setenv("OTEL_SDK_DISABLED", value)
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=abc",
    )
    assert telemetry.init_otel() is False


def test_init_otel_ignores_blank_connection_string(monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "   ")
    assert telemetry.init_otel() is False


def test_init_otel_noop_when_azure_monitor_missing(monkeypatch):
    """ImportError on azure.monitor.opentelemetry yields False, not a crash."""
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=abc",
    )
    # Force the import inside init_otel to fail by removing the module from
    # sys.modules and shadowing the import with a sentinel. Easier: patch
    # the finder so `from azure.monitor.opentelemetry import ...` raises.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("azure.monitor"):
            raise ImportError(f"simulated missing {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert telemetry.init_otel() is False
    assert telemetry.telemetry_enabled is False


def test_init_otel_success_path(monkeypatch):
    """When configure_azure_monitor succeeds, telemetry_enabled flips True."""
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=abc",
    )

    fake_configure = mock.MagicMock()
    fake_module = mock.MagicMock(configure_azure_monitor=fake_configure)

    # Inject a fake azure.monitor.opentelemetry so the import inside
    # init_otel resolves to our mock without touching the real SDK.
    with mock.patch.dict(
        sys.modules,
        {"azure.monitor.opentelemetry": fake_module, "azure.monitor": mock.MagicMock()},
    ):
        result = telemetry.init_otel(service_name="test-svc", service_version="9.9")

    assert result is True
    assert telemetry.telemetry_enabled is True
    assert fake_configure.called
    kwargs = fake_configure.call_args.kwargs
    assert kwargs["connection_string"] == "InstrumentationKey=abc"
    attrs = kwargs["resource_attributes"]
    assert attrs["service.name"] == "test-svc"
    assert attrs["service.version"] == "9.9"
    assert attrs["service.namespace"] == "aaf"


def test_init_otel_configure_exception_is_contained(monkeypatch):
    """If configure_azure_monitor raises, init_otel returns False."""
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=abc",
    )
    fake_configure = mock.MagicMock(side_effect=RuntimeError("network down"))
    fake_module = mock.MagicMock(configure_azure_monitor=fake_configure)
    with mock.patch.dict(
        sys.modules,
        {"azure.monitor.opentelemetry": fake_module, "azure.monitor": mock.MagicMock()},
    ):
        assert telemetry.init_otel() is False
    assert telemetry.telemetry_enabled is False


def test_get_tracer_returns_usable_object():
    tracer = telemetry.get_tracer("test")
    # Whether OTel is installed or not, the tracer must support start_as_current_span.
    assert hasattr(tracer, "start_as_current_span")


def test_noop_span_is_context_manager():
    span = telemetry._NoopSpan()
    with span as s:
        s.set_attribute("k", "v")
        s.set_status("ok")
        s.record_exception(RuntimeError("boom"))
        assert s is span


def test_noop_tracer_yields_noop_span():
    tracer = telemetry._NoopTracer()
    with tracer.start_as_current_span("any") as span:
        # Should not raise regardless of what we call.
        span.set_attribute("run_id", "abc")
        span.set_status("ok")


def test_get_tracer_without_otel(monkeypatch):
    """If opentelemetry is not importable, get_tracer returns _NoopTracer."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            raise ImportError(f"simulated missing {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    tracer = telemetry.get_tracer("noop-case")
    assert isinstance(tracer, telemetry._NoopTracer)
