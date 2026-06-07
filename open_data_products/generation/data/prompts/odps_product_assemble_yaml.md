# Assemble ODPS Product YAML

Assemble one valid ODPS OpenDataProduct YAML document from the minimal ODPS
document and drafted component YAML.

Output rules:

- Return valid YAML only.
- Return exactly one OpenDataProduct document.
- Keep the existing `schema`, `version`, and required `product` fields.
- Add drafted components directly under `product`.
- Preserve component object shapes. Do not collapse components to scalar
  strings.
- Keep `SLA` and `dataQuality` dimensions limited to the ODPS dimension names
  shown in the drafted components. Do not add invented nested rule, monitoring,
  scope, or support fields while assembling.
- Preserve ODPS schema component shapes: `SLA.declarative` and
  `dataQuality.declarative` are named mappings such as `default` and
  `premium`. Do not create `profiles` under either component.
- Preserve pricing plan references to named packages with `paymentGateway`,
  `dataQuality`, `SLA`, and `access` objects. Do not create pricing `$ref`
  values ending in numeric indexes such as `/0`; use named endings such as
  `default`, `premium`, or `API`.
- Preserve `productStrategy`, `dataHolder`, `paymentGateways`, and `license`
  as ODPS objects when drafted. For `license`, use `scope`, `termination`, and
  `governance`; do not emit legacy license fields.
- Do not include `reviewNotes`, `evidenceGaps`, or `draftedComponents` in the
  final ODPS YAML document.
- Do not include Markdown fences or explanatory prose.

Target ODPS v4.1 component shape:

```yaml
product:
  productStrategy:
    status: Planned
    objectives:
      - en: Reduce avoidable churn in strategic customer segments.
    contributesToKPI:
      id: KPI-NET-REVENUE-RETENTION
      name: Net revenue retention
      unit: percentage
      target: 108
    productKPIs:
      - id: KPI-HEALTH-SIGNAL-COVERAGE
        name: Health signal coverage
        unit: percentage
        target: 95
        calculation: accounts with current health indicators divided by active customer accounts
  dataHolder:
    legalName: Example Data Products Ltd
    contactName: Data Product Owner
    email: data-products@example.com
    businessDomain: Revenue Operations
  dataAccess:
    API:
      name:
        en: API
      description:
        en: Authenticated API for account health indicators.
      outputPortType: API
      format: JSON
      authenticationMethod: OAuth
  SLA:
    declarative:
      default:
        name:
          en: The Basic SLA
        dimensions:
          - dimension: uptime
            displaytitle:
              en: Uptime
            objective: 90
            unit: percent
            weight: 50
          - dimension: updateFrequency
            objective: 30
            unit: minutes
            weight: 20
  dataQuality:
    declarative:
      default:
        description: The basic data quality package.
        dimensions:
          - dimension: completeness
            displayTitle: Completeness
            objective: 95
            unit: percentage
            weight: 50
            description: Required fields are populated.
  paymentGateways:
    default:
      description:
        en: Internal chargeback or manual billing process.
      type: Custom
      version: v1
  license:
    scope:
      definition: Internal use for customer success, revenue operations, and renewal planning.
      restrictions: No resale or external redistribution.
      geographicalArea:
        - EU
      permanent: false
      exclusive: false
      rights:
        - Display
        - Distribution
    termination:
      noticePeriod: 30
      terminationConditions: Access ends when the consuming team no longer has an approved business purpose.
    governance:
      ownership: Revenue Operations owns commercial use; Data Platform owns technical operations.
      audit: Access and usage are reviewed quarterly.
  pricingPlans:
    declarative:
      en:
        - name: Internal Starter
          priceCurrency: EUR
          price: "0"
          billingDuration: month
          unit: On-request
          paymentGateway:
            $ref: "#/product/paymentGateways/default"
          dataQuality:
            $ref: "#/product/dataQuality/declarative/default"
          SLA:
            $ref: "#/product/SLA/declarative/default"
          access:
            $ref: "#/product/dataAccess/API"
```

Minimal ODPS document:

```yaml
{minimal_odps}
```

Drafted components:

```yaml
{component_draft}
```

Extracted facts:

```yaml
{product_facts}
```

Source documents:

```text
{source_documents}
```
