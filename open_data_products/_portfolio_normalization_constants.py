"""Constants used by Portfolio ODPS output normalization."""

ODPS_STATUSES = {
    "announcement",
    "draft",
    "development",
    "testing",
    "acceptance",
    "production",
    "sunset",
    "retired",
}
ODPS_STATUS_ALIASES = {
    "proposed": "draft",
    "planned": "announcement",
    "planning": "announcement",
    "active": "production",
    "completed": "production",
    "paused": "sunset",
    "deprecated": "sunset",
    "archived": "retired",
}
ODPS_VISIBILITIES = {"private", "invitation", "organisation", "dataspace", "public"}
ODPS_VISIBILITY_ALIASES = {
    "internal": "organisation",
    "organization": "organisation",
    "organisation": "organisation",
    "restricted": "invitation",
    "external": "public",
    "open": "public",
}
ODPS_PRICING_UNITS = {
    "One-time-payment",
    "Pay-per-use",
    "Recurring",
    "Revenue-sharing",
    "Data-volume",
    "Pay-what-you-want",
    "Freemium",
    "Open-data",
    "Value-based",
    "On-request",
    "Trial",
}
ODPS_PRICING_UNIT_ALIASES = {
    "free": "Open-data",
    "open": "Open-data",
    "subscription": "Recurring",
    "monthly": "Recurring",
    "month": "Recurring",
    "usage": "Pay-per-use",
    "request": "Pay-per-use",
}
