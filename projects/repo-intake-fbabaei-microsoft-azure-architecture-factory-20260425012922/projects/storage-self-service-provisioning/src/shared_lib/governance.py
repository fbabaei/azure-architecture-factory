from __future__ import annotations

import re

from .config import Settings
from .models import ProvisioningRequest


_name_pattern = re.compile(r"^[a-z0-9-]{3,24}$")


def validate_request_policy(request: ProvisioningRequest, settings: Settings) -> None:
    if request.data_class not in settings.allowed_data_classes:
        raise ValueError(f"data_class must be one of {settings.allowed_data_classes}")
    if not _name_pattern.match(request.project):
        raise ValueError("project must match ^[a-z0-9-]{3,24}$")
    if not _name_pattern.match(request.team):
        raise ValueError("team must match ^[a-z0-9-]{3,24}$")


def build_storage_name(request: ProvisioningRequest) -> str:
    return f"st{request.project[:8]}{request.environment}"[:24]


def build_adls_container_name(request: ProvisioningRequest) -> str:
    return f"{request.team}-{request.environment}-{request.data_class}"[:63]
