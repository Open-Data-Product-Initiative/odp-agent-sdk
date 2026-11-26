"""Contract and registry for first-party platform adapters."""

from abc import ABC, abstractmethod
from typing import Dict

from .config import ConnectionProfile, IntegrationError


class PlatformAdapter(ABC):
    """Common lifecycle and safety boundary for platform adapters."""

    def __init__(self, profile: ConnectionProfile):
        self.profile = profile

    def require_write_access(self) -> None:
        """Enforce the local read-only guard before a future write request."""
        if self.profile.read_only:
            raise IntegrationError("The connection is configured read-only")

    @abstractmethod
    def capabilities(self) -> Dict[str, object]:
        """Describe implemented capabilities and known platform evidence."""

    @abstractmethod
    def check_connection(self) -> Dict[str, str]:
        """Perform a safe connectivity check."""

    def discover_context(self, *, product_id=None, query=None, limit=20):
        """Return bounded, read-only metadata evidence when advertised as supported."""
        raise IntegrationError(
            "The selected integration does not support metadata discovery"
        )

    @abstractmethod
    def close(self) -> None:
        """Release adapter resources."""


def open_integration(profile: ConnectionProfile) -> PlatformAdapter:
    """Create a registered first-party adapter for a profile."""
    if profile.platform == "openmetadata":
        from .openmetadata import OpenMetadataAdapter

        return OpenMetadataAdapter(profile)
    raise IntegrationError("Connection adapter is unavailable")
