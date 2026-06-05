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
- If the source lacks details, draft conservative review-needed values.
- Put uncertainty in `reviewNotes` and `evidenceGaps`, not as YAML comments.
- Do not return a full OpenDataProduct document from this step.
- For `SLA`, use only allowed SLA dimension names: `latency`, `uptime`,
  `responseTime`, `errorRate`, `endOfSupport`, `endOfLife`,
  `updateFrequency`, `timeToDetect`, `timeToNotify`, `timeToRepair`,
  `emailResponseTime`. Use `uptime` instead of availability and
  `updateFrequency` instead of data freshness. Do not invent fields such as
  `scope` or freeform nested `support.description`. Use `SLA.declarative` as
  an array of packages; do not use `SLA.profiles`.
- For `dataQuality`, use only allowed data quality dimension names:
  `accuracy`, `completeness`, `conformity`, `consistency`, `coverage`,
  `timeliness`, `validity`, `uniqueness`. Use `timeliness` instead of
  freshness. Do not invent nested `validationRules` or freeform `monitoring`
  objects. Use `dataQuality.declarative` as an array of packages; do not use
  `dataQuality.profiles`.
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
      - name:
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

Pricing plans can link to named generated packages:

```yaml
components:
  pricingPlans:
    declarative:
      en:
        - name: Review Needed Starter
          priceCurrency: USD
          price: "0"
          unit: On-request
          dataQuality:
            $ref: "#/product/dataQuality/default"
          SLA:
            $ref: "#/product/SLA/default"
          access:
            $ref: "#/product/dataAccess/API"
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
