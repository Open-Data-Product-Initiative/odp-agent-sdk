# Changelog

## 0.7.0

- Add pinned offline DPROD 1.0 Beta 2 ingestion, SHACL validation, catalog
  intelligence, DPROD-to-ODPS drafting, and deterministic ODPS-to-DPROD Turtle
  and JSON-LD export.
- Reject the non-normative DPROD development namespace rather than mixing it
  with the OMG Beta 2 vocabulary.
- Add `pyshacl>=0.28.1,<0.29.0` for local normative SHACL evaluation.
- Preserve mapping classifications and loss records; DPROD and ODPS coverage
  is not asserted as equivalent.
- Extend the clean-wheel CI smoke test to load DPROD assets and cross-check an
  exported graph with SHA-512-verified Apache Jena SHACL.
