"""Errors for optional Data Contract integration."""

INSTALL_HINT = "Install with: pip install open-data-products[contracts]"


class ContractIntegrationError(RuntimeError):
    """Base error for Data Contract integration failures."""


class ContractToolUnavailableError(ContractIntegrationError):
    """Raised when datacontract-cli is not available."""
