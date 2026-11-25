# Contract Portfolio Discovery Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Discover evidence-backed, review-only data-product portfolio candidates from ODCS repositories with a future-ready API-source configuration boundary.

**Architecture:** A new module in open_data_products.contracts owns source scanning, normalized inventory, deterministic analysis, report writing, and optional AI proposals. Portfolio adds comparison and review fragments only. The Python, CLI, and MCP surfaces delegate to one facade. API sources are validated configuration but never make network calls in this release.

**Tech Stack:** Python 3.8+, dataclasses, PyYAML, optional datacontract-cli adapter, argparse, stdio JSON-RPC MCP, pytest.

---

## File structure

- Create: open_data_products/contracts/discovery.py — scanning, analysis, artifacts, AI proposals.
- Modify: open_data_products/contracts/models.py — discovery data models.
- Modify: open_data_products/contracts/__init__.py and open_data_products/__init__.py — explicit exports.
- Modify: open_data_products/generation/models.py, open_data_products/generation/__init__.py, and open_data_products/generation/generation.config.yaml — safe portfolio.contractSources configuration.
- Modify: open_data_products/portfolio.py, open_data_products/cli.py, open_data_products/mcp/tools.py, and open_data_products/mcp/manifest.py.
- Create: tests/test_contract_discovery.py; modify tests/test_generation_prompts.py, tests/test_functional_cli.py, tests/test_functional_mcp.py, and tests/test_agentic_patterns.py.
- Modify: README.md and docs/user/data-contracts.md.

### Task 1: Validate configured discovery sources

**Files:**
- Modify: tests/test_generation_prompts.py
- Modify: open_data_products/generation/models.py
- Modify: open_data_products/generation/__init__.py
- Modify: open_data_products/generation/generation.config.yaml

- [ ] **Step 1: Write failing configuration tests.**

~~~python
def test_generation_config_accepts_api_contract_source(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path,
        credentials_ref="env:CONTRACT_REGISTRY_TOKEN",
    )
    assert validate_config(config_path=config)["valid"] is True


@pytest.mark.parametrize("ref", ["token", "env:bad-name", "env:sk-secret"])
def test_generation_config_rejects_invalid_contract_source_credentials(
    tmp_path: Path, ref: str
) -> None:
    config = _write_config(tmp_path, credentials_ref=ref)
    assert any(
        "credentialsRef" in error
        for error in validate_config(config_path=config)["errors"]
    )
~~~

- [ ] **Step 2: Run the focused test.**

Run: pytest tests/test_generation_prompts.py -k contract_source -q

Expected: FAIL because portfolio.contractSources is unknown.

- [ ] **Step 3: Add source models and strict configuration validation.**

~~~python
@dataclass(frozen=True)
class ContractSourceSettings:
    """Configured contract discovery source without credential values."""

    source_id: str
    source_type: str
    endpoint: Optional[str] = None
    credentials_ref: Optional[str] = None
    authentication_type: Optional[str] = None
    documents_selector: Optional[str] = None
    pagination_type: Optional[str] = None
    next_selector: Optional[str] = None
~~~

Add contract_sources to GenerationSettings. Extend the portfolio allowlist with contractSources. Permit source types directory and api. Require API credentialsRef to be env:NAME with an uppercase environment-variable name. Reject raw token, key, authorization, and bearer values or credential-bearing endpoints. Add _resolve_contract_sources() and return safe summaries from get_config().

- [ ] **Step 4: Add the safe template example.**

~~~yaml
portfolio:
  contractSources:
    contracts-api:
      type: api
      endpoint: https://contracts.example.org/api/contracts
      credentialsRef: env:ODP_CONTRACTS_API_TOKEN
      authentication:
        type: bearer
      documentsSelector: items
      pagination:
        type: cursor
        nextSelector: nextCursor
~~~

- [ ] **Step 5: Verify and commit.**

Run: pytest tests/test_generation_prompts.py -q

Expected: PASS.

~~~bash
git add open_data_products/generation tests/test_generation_prompts.py
git commit -m "feat: configure contract discovery sources"
~~~

### Task 2: Define the discovery result contract and public facade

**Files:**
- Create: tests/test_contract_discovery.py
- Modify: open_data_products/contracts/models.py
- Modify: open_data_products/contracts/__init__.py
- Modify: open_data_products/__init__.py

- [ ] **Step 1: Write failing model and export tests.**

~~~python
def test_discovery_result_serializes_metadata_not_document_bodies() -> None:
    result = ContractDiscoveryResult(
        source_id="contracts", inventory=[], relationships=[], candidates=[]
    )
    payload = result.to_dict()
    assert payload["kind"] == "ContractDiscovery"
    assert "document" not in json.dumps(payload)


def test_discovery_api_is_explicitly_exported() -> None:
    from open_data_products import discover_contract_portfolio
    assert callable(discover_contract_portfolio)
~~~

- [ ] **Step 2: Run the focused test.**

Run: pytest tests/test_contract_discovery.py -k 'serializes or exported' -q

Expected: FAIL with missing models and facade.

- [ ] **Step 3: Add immutable records and exports.**

~~~python
@dataclass(frozen=True)
class ContractDiscoveryRequest:
    """Request for deterministic contract portfolio discovery."""

    output: PathLike
    directory: Optional[PathLike] = None
    source_id: Optional[str] = None
    portfolio_path: Optional[PathLike] = None
    use_ai: bool = False


@dataclass(frozen=True)
class ContractInventoryRecord:
    """Technical evidence found for one source contract."""

    logical_id: str
    source_reference: str
    status: str
    odcs_version: Optional[str] = None
    findings: List[Finding] = field(default_factory=list)
~~~

Define ContractRelationship, ProductCandidate, DiscoveryArtifact, and ContractDiscoveryResult. Each to_dict() includes IDs, evidence class, rationale, and findings but never raw documents or absolute paths. Export discover_contract_portfolio from both package init files.

- [ ] **Step 4: Verify and commit.**

Run: pytest tests/test_contract_discovery.py -k 'serializes or exported' -q

Expected: PASS.

~~~bash
git add open_data_products/__init__.py open_data_products/contracts tests/test_contract_discovery.py
git commit -m "feat: define contract discovery models"
~~~

### Task 3: Scan local contract repositories safely

**Files:**
- Modify: tests/test_contract_discovery.py
- Create: open_data_products/contracts/discovery.py

- [ ] **Step 1: Write a failing mixed-input test.**

~~~python
def test_discovery_keeps_valid_invalid_and_unsupported_records(tmp_path: Path) -> None:
    (tmp_path / "orders.yaml").write_text(
        "apiVersion: v3.2.0\nkind: DataContract\nid: orders\nmodels: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "notes.yaml").write_text("title: notes\n", encoding="utf-8")
    result = discover_contract_portfolio(directory=tmp_path, output=tmp_path / "out")
    assert {item.status for item in result.inventory} == {
        "loaded", "invalid", "unsupported"
    }
~~~

- [ ] **Step 2: Run the test.**

Run: pytest tests/test_contract_discovery.py::test_discovery_keeps_valid_invalid_and_unsupported_records -q

Expected: FAIL because the facade has no implementation.

- [ ] **Step 3: Implement the directory adapter and facade.**

~~~python
def discover_contract_portfolio(
    *,
    output: PathLike,
    directory: Optional[PathLike] = None,
    source_id: Optional[str] = None,
    portfolio_path: Optional[PathLike] = None,
    use_ai: bool = False,
    client: Optional[Callable[[str, str], str]] = None,
    source_settings: Optional[Mapping[str, ContractSourceSettings]] = None,
) -> ContractDiscoveryResult:
    """Discover review-only candidates from exactly one contract source."""
~~~

Require exactly one of directory and source_id. Recursively process YAML and JSON, use existing loader, summary, and schema extractor, detect ODCS from apiVersion and kind DataContract, and convert malformed, unreadable, or unsupported input into findings. Record optional validation as passed, failed, or unavailable. Use relative references and hash-derived logical IDs.

- [ ] **Step 4: Add future-source and provenance tests.**

~~~python
def test_api_source_is_not_implemented_and_makes_no_request(tmp_path: Path) -> None:
    result = discover_contract_portfolio(
        source_id="registry",
        source_settings={"registry": ContractSourceSettings("registry", "api")},
        output=tmp_path / "out",
    )
    assert result.source_status == "source_not_implemented"


def test_inventory_uses_relative_source_references(tmp_path: Path) -> None:
    contracts = tmp_path / "contracts"
    (contracts / "nested").mkdir(parents=True)
    _write_odcs(contracts / "nested" / "orders.yaml")
    result = discover_contract_portfolio(directory=contracts, output=tmp_path / "out")
    assert result.inventory[0].source_reference == "nested/orders.yaml"
    assert str(contracts) not in json.dumps(result.to_dict())
~~~

- [ ] **Step 5: Verify and commit.**

Run: pytest tests/test_contract_discovery.py -q

Expected: PASS.

~~~bash
git add open_data_products/contracts/discovery.py tests/test_contract_discovery.py
git commit -m "feat: inventory ODCS contract repositories"
~~~

### Task 4: Analyze evidence and write review artifacts

**Files:**
- Modify: tests/test_contract_discovery.py
- Modify: open_data_products/contracts/discovery.py
- Modify: open_data_products/portfolio.py

- [ ] **Step 1: Write failing duplicate, overlap, and boundary tests.**

~~~python
def test_discovery_labels_exact_duplicates_and_schema_overlap(tmp_path: Path) -> None:
    _write_contract(tmp_path / "a.yaml", ODCS_ORDERS)
    _write_contract(tmp_path / "b.yaml", ODCS_ORDERS)
    _write_contract(tmp_path / "c.yaml", ODCS_ORDERS_OVERLAP)
    result = discover_contract_portfolio(directory=tmp_path, output=tmp_path / "out")
    assert any(
        item.kind == "exact_duplicate" and item.evidence_class == "inferred"
        for item in result.relationships
    )
    assert any(
        item.kind == "schema_overlap" and item.evidence_class == "inferred"
        for item in result.relationships
    )
    assert all(item.status == "proposed" for item in result.candidates)
~~~

- [ ] **Step 2: Run the test.**

Run: pytest tests/test_contract_discovery.py -k duplicates_and_schema_overlap -q

Expected: FAIL because no relationships or candidates are calculated.

- [ ] **Step 3: Implement deterministic evidence rules.**

~~~python
def _canonical_contract_hash(document: Mapping[str, object]) -> str:
    """Return a stable hash for a normalized contract mapping."""


def _analyze_inventory(
    inventory: Sequence[ContractInventoryRecord],
) -> Tuple[List[ContractRelationship], List[ProductCandidate]]:
    """Produce explainable technical evidence and proposed candidates."""
~~~

Use canonical sorted mappings for exact duplicates and model-field-type signatures for overlap. Label declared relationship and dependency references explicit; label owner, domain, and schema similarities inferred. Candidates retain rule score, supporting IDs, rationale, and unresolved questions about objective, consumer need, ownership, and product boundary. All candidates remain proposed.

- [ ] **Step 4: Write failing artifact tests.**

~~~python
def test_discovery_writes_deterministic_json_and_safe_html(tmp_path: Path) -> None:
    output = tmp_path / "out"
    _write_contract(tmp_path / "unsafe.yaml", ODCS_WITH_HTML_DESCRIPTION)
    discover_contract_portfolio(directory=tmp_path, output=output)
    first = (output / "product-candidates.json").read_bytes()
    discover_contract_portfolio(directory=tmp_path, output=output)
    assert first == (output / "product-candidates.json").read_bytes()
    assert json.loads((output / "contract-inventory.json").read_text())["kind"] == "ContractInventory"
    assert "&lt;script&gt;" in (output / "discovery-report.html").read_text()
~~~

- [ ] **Step 5: Implement writers and review fragments.**

~~~python
def _write_discovery_artifacts(
    result: ContractDiscoveryResult, output: Path
) -> List[DiscoveryArtifact]:
    """Write deterministic JSON, HTML, and review-only fragments."""
~~~

Write sorted JSON named contract-inventory.json and product-candidates.json, escape report values with html.escape, and return logical artifact IDs. Add one narrow portfolio helper that converts only evidence-qualified details into review-only ODPC or ODPG fragments. Omit a fragment if it would require invented business facts. Compare candidates with an optional existing portfolio through existing ODPC loaders.

- [ ] **Step 6: Verify and commit.**

Run: pytest tests/test_contract_discovery.py -q

Expected: PASS.

~~~bash
git add open_data_products/contracts/discovery.py open_data_products/portfolio.py tests/test_contract_discovery.py
git commit -m "feat: analyze contract portfolio evidence"
~~~

### Task 5: Add evidence-bound AI proposals

**Files:**
- Modify: tests/test_contract_discovery.py
- Modify: open_data_products/contracts/discovery.py

- [ ] **Step 1: Write the failing AI test.**

~~~python
def test_ai_proposals_are_traceable_and_not_confirmed(tmp_path: Path) -> None:
    result = discover_contract_portfolio(
        directory=_write_overlap_fixture(tmp_path),
        output=tmp_path / "out",
        use_ai=True,
        client=lambda prompt, model: (
            '{"suggestions":[{"contractIds":["orders-a","orders-b"],'
            '"rationale":"shared order model"}]}'
        ),
    )
    assert result.ai_proposals[0].status == "proposed"
    assert result.ai_proposals[0].supporting_contract_ids == ["orders-a", "orders-b"]
~~~

- [ ] **Step 2: Run the test.**

Run: pytest tests/test_contract_discovery.py -k ai_proposals -q

Expected: FAIL because AI proposals are absent.

- [ ] **Step 3: Implement a defensive proposal parser.**

~~~python
def _propose_candidates_with_ai(
    inventory: Sequence[ContractInventoryRecord],
    client: Callable[[str, str], str],
    model: str,
) -> List[ProductCandidate]:
    """Return review-only suggestions tied to known inventory IDs."""
~~~

Prompt with normalized inventory only. Reject unknown IDs, missing rationales, and malformed JSON. Mark valid suggestions proposed and retain unresolved business questions. A provider failure adds a redacted warning while deterministic artifacts are still written.

- [ ] **Step 4: Verify and commit.**

Run: pytest tests/test_contract_discovery.py -q

Expected: PASS.

~~~bash
git add open_data_products/contracts/discovery.py tests/test_contract_discovery.py
git commit -m "feat: add evidence-bound AI discovery proposals"
~~~

### Task 6: Expose CLI and MCP consistently

**Files:**
- Modify: tests/test_functional_cli.py
- Modify: tests/test_functional_mcp.py
- Modify: tests/test_agentic_patterns.py
- Modify: open_data_products/cli.py
- Modify: open_data_products/mcp/tools.py
- Modify: open_data_products/mcp/manifest.py

- [ ] **Step 1: Write failing CLI behavior tests.**

~~~python
def test_portfolio_discover_contracts_writes_review_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contracts = _write_cli_contracts(tmp_path)
    output = tmp_path / "discovery"
    assert main([
        "portfolio", "discover-contracts", str(contracts),
        "--output", str(output), "--json",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "ContractDiscovery"
    assert (output / "contract-inventory.json").is_file()
~~~

- [ ] **Step 2: Verify RED.**

Run: pytest tests/test_functional_cli.py -k discover_contracts -q

Expected: FAIL because the subcommand is missing.

- [ ] **Step 3: Add parser and handler.**

~~~python
discover_parser = portfolio_subparsers.add_parser(
    "discover-contracts",
    help="Discover review-only candidates from ODCS contracts",
)
discover_parser.add_argument("contracts", nargs="?")
discover_parser.add_argument("--source")
discover_parser.add_argument("--output", "-o", required=True)
discover_parser.add_argument("--portfolio")
discover_parser.add_argument("--ai", action="store_true")
discover_parser.add_argument("--strict-validation", action="store_true")
discover_parser.add_argument("--json", action="store_true")
~~~

Require exactly one input. Construct a generation client only when AI is selected. JSON output has logical artifact counts and statuses only. Strict validation is non-zero for failed or unavailable external ODCS validation.

- [ ] **Step 4: Write failing MCP tests.**

~~~python
def test_discover_contract_portfolio_requires_approval(tmp_path: Path) -> None:
    tool = _tool("discover_contract_portfolio")
    handler = tool["handler"]
    with pytest.raises(ValueError, match="approved must be true"):
        handler({"directory": str(tmp_path), "output": str(tmp_path / "out")})


def test_discover_contract_portfolio_redacts_workspace_paths(tmp_path: Path) -> None:
    result = _call_tool("discover_contract_portfolio", {
        "directory": str(_write_mcp_contracts(tmp_path)),
        "output": str(tmp_path / "out"),
        "approved": True,
    })
    assert str(tmp_path) not in result["content"][0]["text"]
~~~

- [ ] **Step 5: Run the MCP test.**

Run: pytest tests/test_functional_mcp.py -k discover_contract_portfolio -q

Expected: FAIL because the tool is absent.

- [ ] **Step 6: Implement the state-changing tool.**

~~~python
def _h_discover_contract_portfolio(args: Dict[str, Any]) -> Dict[str, Any]:
    """Write discovery artifacts only after explicit approval."""
    if args.get("approved") is not True:
        raise ValueError("approved must be true before discovery may write artifacts")
    result = discover_contract_portfolio(
        directory=args.get("directory"),
        source_id=args.get("source"),
        output=args["output"],
        portfolio_path=args.get("portfolio"),
    )
    return _json_envelope(_contract_discovery_summary(result))
~~~

Require output and approved, allow exactly one source input, classify it state-changing, and add it to the manifest and agentic-pattern expected tools. Return logical IDs, statuses, counts, and redacted findings only.

- [ ] **Step 7: Verify and commit.**

Run: pytest tests/test_functional_cli.py tests/test_functional_mcp.py tests/test_agentic_patterns.py -q

Expected: PASS.

~~~bash
git add open_data_products/cli.py open_data_products/mcp tests/test_functional_cli.py tests/test_functional_mcp.py tests/test_agentic_patterns.py
git commit -m "feat: expose contract discovery interfaces"
~~~

### Task 7: Document and release-gate the feature

**Files:**
- Modify: README.md
- Modify: docs/user/data-contracts.md

- [ ] **Step 1: Add documentation coverage.**

~~~python
def test_readme_includes_contract_portfolio_discovery() -> None:
    content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "portfolio discover-contracts" in content
~~~

- [ ] **Step 2: Verify RED.**

Run: pytest tests/test_functional_cli.py -k contract_portfolio_discovery -q

Expected: FAIL until the command is documented.

- [ ] **Step 3: Document supported behavior only.**

Document deterministic scanning, artifacts, explicit/inferred/proposed evidence, product-manager approval, optional validation and AI, portfolio comparison, and validated-but-not-runnable API source settings. State that generation.config.yaml references environment variables; artifacts and MCP exclude credentials and complete contract bodies.

- [ ] **Step 4: Run release gates.**

~~~bash
pytest -q
python -c "import open_data_products"
python -m open_data_products.cli manifest --json | python -m json.tool
git diff --check
~~~

Expected: all tests pass, import exits zero, manifest parses, and diff check is clean.

- [ ] **Step 5: Commit docs and planning artifacts.**

~~~bash
git add README.md docs/user/data-contracts.md docs/planning/contract-portfolio-discovery-design.md docs/planning/contract-portfolio-discovery-implementation-plan.md
git commit -m "docs: document contract portfolio discovery"
~~~
