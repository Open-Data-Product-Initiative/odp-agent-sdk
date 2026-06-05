# ODPS Validation Development Notes

This page explains the ODPS validation path for contributors. The important
idea is that ODPS validation has two layers: raw document shape checks and SDK
model validation.

## Main Code Paths

ODPS document handling is split across:

- `open_data_products/agent.py`: cross-spec detection and public
  `validate_document()`.
- `open_data_products/odps/core.py`: `OpenDataProduct` loading, validation,
  serialization, and component helpers.
- `open_data_products/odps/codecs.py`: conversion between YAML dictionaries
  and dataclasses.
- `open_data_products/odps/models.py`: dataclasses for product details and
  optional components.
- `open_data_products/odps/validation.py`: rule-based SDK validation.
- `open_data_products/odps/data/schema/odps.json`: bundled raw schema.

## Validation Flow

`validate_document(path_or_document)` detects ODPS documents when the schema
contains `odps` or a mapping has a top-level `product` key.

For ODPS, validation runs in this order:

1. Load or accept the raw mapping.
2. If the document is ODPS v4.1, run raw schema validation and additional v4.1
   shape checks in `agent.py`.
3. Parse the mapping into `OpenDataProduct` with `OpenDataProduct.from_dict()`.
4. Run `OpenDataProduct.validate()`.
5. Return a shared `ValidationResult`.

Raw checks catch schema-facing problems before the SDK model can silently
normalize or ignore them.

## Raw V4.1 Shape Checks

The helper `_validate_odps_v41_shape()` enforces SDK-specific v4.1 migration
rules that are easy for agents and LLMs to miss:

- product details must be under `product.details.<language>`;
- legacy flat fields such as `productID`, `name`, `visibility`, `status`, and
  `type` must not remain directly under `product`;
- `pricingPlans` must use `declarative` or `executable`, not legacy `plans`;
- `dataContract` is rejected in favor of `contract`.

Add new raw-shape checks here only when the problem is visible in the raw YAML
and should fail before model parsing.

## Codecs

`codecs.py` is the compatibility boundary. It accepts schema-facing YAML and
maps it into SDK dataclasses. This is where contributors should handle known
shape variations.

Examples:

- `parse_product_details()` accepts `product.details.en` and older flat product
  fields.
- `parse_pricing_plans()` accepts `pricingPlans.declarative`.
- `parse_sla()` and `parse_data_quality()` accept schema-facing `declarative`
  arrays and map them into internal profile dictionaries.
- `parse_data_access()` accepts both legacy SDK object shape and v4.1 list
  shape.

Do not add prompt- or LLM-specific cleanup in codecs. That belongs in the
generation normalization layer.

## SDK Model Validation

`OpenDataProduct.validate()` runs `ODPSValidationFramework`, which applies rule
objects such as:

- `RequiredFieldsValidator`
- `EnumFieldsValidator`
- `DataAccessValidator`
- `LicenseValidator`
- `LanguageCodesValidator`
- `DataHolderValidator`
- `URLValidator`
- `DateValidator`
- `PricingPlansValidator`
- `PaymentGatewaysValidator`
- `ProductStrategyValidator`

These validators operate on parsed dataclasses, not the raw YAML. Use them for
semantic checks, code format checks, enum checks, URL checks, and cross-field
constraints after parsing.

## Schema Vs SDK Shape

The SDK must handle two related but different shapes:

- Schema-facing ODPS YAML, which contributors should prefer in examples,
  prompts, and generated documents.
- Internal SDK dataclasses, which make Python access and validation easier.

Do not expose internal shapes such as `SLA.profiles` or
`dataQuality.profiles` in generated YAML examples. Use schema-facing
`SLA.declarative` and `dataQuality.declarative`.

Known compatibility note: the bundled ODPS schema and SDK parser currently
disagree about `dataAccess` object versus array shape. Keep changes around this
area narrow and add tests for both raw validation and SDK parsing.

## Tests

Use these files when changing ODPS validation behavior:

- `tests/test_agent_api.py` for cross-spec validation and raw-shape behavior.
- `tests/test_core.py` for `OpenDataProduct.from_dict()` and SDK model
  compatibility.
- `tests/test_validation.py` for rule-based validation.
- `tests/test_generation_prompts.py` when generation normalization must produce
  ODPS-valid YAML.

Always add a failing regression first when changing accepted schema shapes,
rejected legacy shapes, or parser compatibility.

