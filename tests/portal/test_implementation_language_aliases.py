from __future__ import annotations

import start_factory_portal as portal


def test_sanitize_implementation_language_accepts_python_dotnet() -> None:
    assert portal._sanitize_implementation_language("python") == "python"
    assert portal._sanitize_implementation_language("dotnet") == "dotnet"


def test_sanitize_implementation_language_maps_csharp_aliases_to_dotnet() -> None:
    assert portal._sanitize_implementation_language("csharp") == "dotnet"
    assert portal._sanitize_implementation_language("C#") == "dotnet"
    assert portal._sanitize_implementation_language(".net") == "dotnet"
    assert portal._sanitize_implementation_language("aspnetcore") == "dotnet"


def test_sanitize_implementation_language_rejects_unknown_values() -> None:
    assert portal._sanitize_implementation_language("java") is None
    assert portal._sanitize_implementation_language("") is None
    assert portal._sanitize_implementation_language(None) is None
