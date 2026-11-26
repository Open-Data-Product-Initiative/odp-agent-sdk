"""Errors for optional Data Contract integration."""

INSTALL_HINT = (
    "On Python 3.8–3.12, install with: pip install 'open-data-products[contracts]'. "
    "On Python 3.13 or later the extra does not install datacontract-cli; "
    "use a compatible separate environment and put its datacontract executable on PATH."
)


class ContractIntegrationError(RuntimeError):
    """Base error for Data Contract integration failures."""


class ContractToolUnavailableError(ContractIntegrationError):
    """Raised when datacontract-cli is not available."""
