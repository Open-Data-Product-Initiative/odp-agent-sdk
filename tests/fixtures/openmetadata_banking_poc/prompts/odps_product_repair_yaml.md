# Repair ODPS Product YAML

Repair one ODPS OpenDataProduct YAML document so it satisfies the validation
errors.

Output rules:

- Return valid YAML only.
- Return exactly one repaired OpenDataProduct document.
- Preserve supported content from the generated document.
- Change only what is needed to fix the validation errors.
- Do not include Markdown fences or explanatory prose.

Generated ODPS document:

```yaml
{generated_odps}
```

Validation errors:

```text
{validation_errors}
```
