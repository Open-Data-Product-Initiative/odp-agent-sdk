# Draft ODPS Product Components

Draft the requested ODPS product components as valid YAML.

Output rules:

- Return valid YAML only.
- Draft only the requested ODPS product components.
- The requested ODPS product components belong under the `product` object in
  the final OpenDataProduct document.
- Every component value must be an object or array matching the ODPS shape.
  Never return scalar strings for components such as `license`, `dataHolder`,
  `contract`, `SLA`, `dataQuality`, `pricingPlans`, `dataAccess`,
  `paymentGateways`, or `productStrategy`.
- If a requested optional component lacks enough source evidence for a useful
  schema-shaped draft, omit that component from `components` and record the gap
  in `evidenceGaps`. Do not create placeholder component objects only to satisfy
  the request.
- Put uncertainty in `reviewNotes` and `evidenceGaps`, not as YAML comments.
- Do not return a full OpenDataProduct document from this step.
- For `license`, use ODPS v4.1 `scope`, `termination`, and `governance`.
  Do not emit legacy license fields.
- For `productStrategy`, include schema-shaped objectives, KPIs, and status
  only when the source evidence supports them.
- For `dataHolder`, use contact and legal ownership fields as an object.
- For `paymentGateways`, use named gateway mappings such as `default`.
- For `SLA`, use only allowed SLA dimension names: `latency`, `uptime`,
  `responseTime`, `errorRate`, `endOfSupport`, `endOfLife`,
  `updateFrequency`, `timeToDetect`, `timeToNotify`, `timeToRepair`,
  `emailResponseTime`. Use `uptime` instead of availability and
  `updateFrequency` instead of data freshness. Do not invent fields such as
  `scope` or freeform nested `support.description`. Use `SLA.declarative` as
  a named mapping of packages such as `default` and `premium`; do not use
  `SLA.profiles`.
- For `dataQuality`, use only allowed data quality dimension names:
  `accuracy`, `completeness`, `conformity`, `consistency`, `coverage`,
  `timeliness`, `validity`, `uniqueness`. Use `timeliness` instead of
  freshness. Do not invent nested `validationRules` or freeform `monitoring`
  objects. Use `dataQuality.declarative` as a named mapping of packages such
  as `default` and `premium`; do not use `dataQuality.profiles`.
- For `pricingPlans`, use only ODPS pricing plan fields such as `name`,
  `priceCurrency`, `price`, `billingDuration`, `unit`, and `notes`. Do not use
  invented fields such as `planID`, `currency`, `billingCycle`, `conditions`,
  or nested condition objects. Pricing plans may reference generated packages
  with `paymentGateway`, `dataQuality`, `SLA`, and `access` objects containing
  `$ref` values. These `$ref` values must end in a named package/profile such as
  `default`, `premium`, or `API`; never end a pricing `$ref` in a number such as
  `/0`. If pricing is pending, prefer `unit: On-request` and put uncertainty in
  `notes` and `reviewNotes`.

Required shape:

```yaml
components:
  SLA:
    declarative:
      default:
        name:
          en: Default SLA
        dimensions:
          - dimension: uptime
            objective: 99.5
            unit: percent
draftedComponents:
  - SLA
reviewNotes:
  - SLA drafted because no service-level targets were provided.
evidenceGaps:
  - Missing support hours and escalation process.
```

If none of the requested optional components are supported by source evidence,
return an empty component packet:

```yaml
components: {}
draftedComponents: []
reviewNotes: []
evidenceGaps:
  - Requested components were not supported by the source documents.
```

Contrast examples:

```yaml
# Supported component: source names API access and API-key authentication.
components:
  dataAccess:
    API:
      name:
        en: API
      outputPortType: API
      authenticationMethod: API key
draftedComponents:
  - dataAccess
reviewNotes: []
evidenceGaps: []
```

```yaml
# Unsupported requested component: source has no pricing terms.
components: {}
draftedComponents: []
reviewNotes: []
evidenceGaps:
  - pricingPlans requested, but the source does not state pricing or billing terms.
```

Pricing plans can link to named generated packages:

```yaml
components:
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
        description:
          en: The basic SLA package.
        dimensions:
          - dimension: uptime
            displaytitle:
              en: Uptime
            objective: 90
            unit: percent
            weight: 50
          - dimension: responseTime
            objective: 200
            unit: milliseconds
            weight: 30
          - dimension: updateFrequency
            objective: 30
            unit: minutes
            weight: 20
      premium:
        name:
          en: The Premium SLA
        description:
          en: The Premium SLA package.
        dimensions:
          - dimension: uptime
            displaytitle:
              en: Uptime
            objective: 99
            unit: percent
            weight: 70
          - dimension: responseTime
            objective: 100
            unit: milliseconds
            weight: 20
          - dimension: updateFrequency
            objective: 5
            unit: minutes
            weight: 10
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
      restrictions: No resale, external redistribution, or automated adverse customer decisions without review.
      geographicalArea:
        - EU
      permanent: false
      exclusive: false
      rights:
        - Display
        - Distribution
        - Adaptation
    termination:
      noticePeriod: 30
      terminationConditions: Access ends when the consuming team no longer has an approved business purpose.
    governance:
      ownership: Revenue Operations owns commercial use; Data Platform owns technical operations.
      audit: Access and usage are reviewed quarterly.
  pricingPlans:
    declarative:
      en:
        - name: Review Needed Starter
          priceCurrency: USD
          price: "0"
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

Complete-draft example for the default component set:

```yaml
components:
  SLA:
    declarative:
      default:
        name:
          en: Standard SLA
        description:
          en: Review-needed service level package based on source evidence.
        dimensions:
          - dimension: uptime
            displaytitle:
              en: Uptime
            objective: 99
            unit: percent
            weight: 60
          - dimension: updateFrequency
            displaytitle:
              en: Update Frequency
            objective: 24
            unit: hours
            weight: 40
  dataQuality:
    declarative:
      default:
        description: Review-needed data quality package based on source evidence.
        dimensions:
          - dimension: completeness
            displayTitle: Completeness
            objective: 95
            unit: percentage
            weight: 50
            description: Required fields are populated.
          - dimension: timeliness
            displayTitle: Timeliness
            objective: 24
            unit: hours
            weight: 50
            description: Data is refreshed within the stated reporting window.
  pricingPlans:
    declarative:
      en:
        - name: Review Needed Starter
          priceCurrency: EUR
          price: "0"
          billingDuration: month
          unit: On-request
          notes: Pricing needs human review before publication.
          dataQuality:
            $ref: "#/product/dataQuality/declarative/default"
          SLA:
            $ref: "#/product/SLA/declarative/default"
draftedComponents:
  - SLA
  - dataQuality
  - pricingPlans
reviewNotes:
  - pricingPlans require human review because the source did not state commercial terms.
evidenceGaps:
  - Missing explicit pricing terms.
```

Requested ODPS product components:

```text
{requested_components}
```

Minimal ODPS document:

```yaml
{minimal_odps}
```

Extracted facts:

```yaml
{product_facts}
```

Source documents:

```text
{source_documents}
```
