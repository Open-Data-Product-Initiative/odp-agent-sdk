"""Thin optional adapter around datacontract-cli validation."""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib import metadata, util
from pathlib import Path
from typing import List, Optional, Sequence

from .errors import INSTALL_HINT
from .models import (
    ContractExportResult,
    ContractToolAvailability,
    ContractValidationResult,
    Finding,
)

TOOL_NAME = "datacontract-cli"


def detect_datacontract_cli() -> ContractToolAvailability:
    """Detect whether datacontract-cli is available as a package or command."""
    python_package = util.find_spec("datacontract") is not None
    executable = shutil.which("datacontract")
    return ContractToolAvailability(
        python_package=python_package,
        cli_executable=executable,
        tool_version=_detect_tool_version(),
    )


def validate_contract(path_or_url: str) -> ContractValidationResult:
    """Validate a Data Contract through datacontract-cli when available."""
    availability = detect_datacontract_cli()
    if availability.python_package:
        return _validate_with_python_api(path_or_url, availability.tool_version)
    if availability.cli_executable:
        return _validate_with_cli(
            availability.cli_executable,
            path_or_url,
            availability.tool_version,
        )
    return _missing_dependency_result()


def export_contract(path_or_url: str, format: str = "jsonschema") -> ContractExportResult:
    """Export a Data Contract through datacontract-cli when available."""
    availability = detect_datacontract_cli()
    if availability.python_package:
        return _export_with_python_api(path_or_url, format, availability.tool_version)
    if availability.cli_executable:
        return _export_with_cli(
            availability.cli_executable,
            path_or_url,
            format,
            availability.tool_version,
        )
    return _missing_export_dependency_result(format)


def _validate_with_python_api(
    path_or_url: str,
    tool_version: Optional[str],
) -> ContractValidationResult:
    try:
        from datacontract.data_contract import DataContract  # type: ignore

        contract = DataContract(data_contract_file=path_or_url)
        lint = getattr(contract, "lint", None)
        if lint is None:
            return _validate_with_cli_or_error(path_or_url, tool_version)
        run = lint()
        passed = _run_passed(run)
        findings = _findings_from_run(run)
        if not passed and not findings:
            findings = [
                Finding(
                    code="DATACONTRACT_VALIDATION_FAILED",
                    message="Data Contract validation failed.",
                    severity="error",
                    source=TOOL_NAME,
                )
            ]
        return ContractValidationResult(
            passed=passed,
            tool=TOOL_NAME,
            tool_version=tool_version,
            contract_format=_infer_contract_format(path_or_url),
            findings=findings,
            raw=repr(run),
        )
    except Exception as exc:
        return ContractValidationResult(
            passed=False,
            tool=TOOL_NAME,
            tool_version=tool_version,
            contract_format=_infer_contract_format(path_or_url),
            findings=[
                Finding(
                    code="DATACONTRACT_VALIDATION_ERROR",
                    message=str(exc),
                    severity="error",
                    source=TOOL_NAME,
                )
            ],
        )


def _validate_with_cli_or_error(
    path_or_url: str,
    tool_version: Optional[str],
) -> ContractValidationResult:
    executable = shutil.which("datacontract")
    if executable is None:
        return ContractValidationResult(
            passed=False,
            tool=TOOL_NAME,
            tool_version=tool_version,
            contract_format=_infer_contract_format(path_or_url),
            findings=[
                Finding(
                    code="DATACONTRACT_PYTHON_API_UNSUPPORTED",
                    message=(
                        "Installed datacontract package does not expose lint(); "
                        "install the datacontract CLI executable or upgrade "
                        "datacontract-cli."
                    ),
                    severity="error",
                    source=TOOL_NAME,
                )
            ],
        )
    return _validate_with_cli(executable, path_or_url, tool_version)


def _validate_with_cli(
    executable: str,
    path_or_url: str,
    tool_version: Optional[str],
) -> ContractValidationResult:
    command = [executable, "lint", path_or_url]
    completed = _run_command(command)
    output = "\n".join(
        part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
    )


def _export_with_python_api(
    path_or_url: str,
    format: str,
    tool_version: Optional[str],
) -> ContractExportResult:
    try:
        from datacontract.data_contract import DataContract  # type: ignore

        contract = DataContract(data_contract_file=path_or_url)
        export = getattr(contract, "export", None)
        if export is None:
            return _export_with_cli_or_error(path_or_url, format, tool_version)
        content = export(format=format)
        return _contract_export_result(format, content, tool_version)
    except Exception as exc:
        return ContractExportResult(
            exported=False,
            format=format,
            tool_version=tool_version,
            findings=[
                Finding(
                    code="DATACONTRACT_EXPORT_ERROR",
                    message=str(exc),
                    severity="error",
                    source=TOOL_NAME,
                )
            ],
        )


def _export_with_cli_or_error(
    path_or_url: str,
    format: str,
    tool_version: Optional[str],
) -> ContractExportResult:
    executable = shutil.which("datacontract")
    if executable is None:
        return ContractExportResult(
            exported=False,
            format=format,
            tool_version=tool_version,
            findings=[
                Finding(
                    code="DATACONTRACT_PYTHON_API_UNSUPPORTED",
                    message=(
                        "Installed datacontract package does not expose export(); "
                        "install the datacontract CLI executable or upgrade "
                        "datacontract-cli."
                    ),
                    severity="error",
                    source=TOOL_NAME,
                )
            ],
        )
    return _export_with_cli(executable, path_or_url, format, tool_version)


def _export_with_cli(
    executable: str,
    path_or_url: str,
    format: str,
    tool_version: Optional[str],
) -> ContractExportResult:
    completed = _run_command([executable, "export", "--format", format, path_or_url])
    output = "\n".join(
        part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
    )
    if completed.returncode != 0:
        return ContractExportResult(
            exported=False,
            format=format,
            tool_version=tool_version,
            findings=_findings_from_output(output, completed.returncode),
            raw=output or None,
        )
    return _contract_export_result(format, completed.stdout, tool_version)
    findings = _findings_from_output(output, completed.returncode)
    return ContractValidationResult(
        passed=completed.returncode == 0,
        tool=TOOL_NAME,
        tool_version=tool_version,
        contract_format=_infer_contract_format(path_or_url),
        findings=findings,
        raw=output or None,
    )


def _missing_dependency_result() -> ContractValidationResult:
    return ContractValidationResult(
        passed=False,
        tool=TOOL_NAME,
        findings=[
            Finding(
                code="DATACONTRACT_CLI_NOT_INSTALLED",
                message=f"datacontract-cli is not installed. {INSTALL_HINT}",
                severity="error",
                source=TOOL_NAME,
            )
        ],
    )


def _missing_export_dependency_result(format: str) -> ContractExportResult:
    return ContractExportResult(
        exported=False,
        format=format,
        findings=[
            Finding(
                code="DATACONTRACT_CLI_NOT_INSTALLED",
                message=f"datacontract-cli is not installed. {INSTALL_HINT}",
                severity="error",
                source=TOOL_NAME,
            )
        ],
    )


def _contract_export_result(
    format: str,
    content: object,
    tool_version: Optional[str],
) -> ContractExportResult:
    raw = content if isinstance(content, str) else None
    return ContractExportResult(
        exported=True,
        format=format,
        content=_parse_export_content(content),
        tool_version=tool_version,
        raw=raw,
    )


def _parse_export_content(content: object) -> object:
    if not isinstance(content, str):
        return content
    stripped = content.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return content


def _detect_tool_version() -> Optional[str]:
    for package_name in ("datacontract-cli", "datacontract"):
        try:
            return metadata.version(package_name)
        except metadata.PackageNotFoundError:
            pass
    executable = shutil.which("datacontract")
    if executable is None:
        return None
    try:
        completed = _run_command([executable, "--version"])
    except OSError:
        return None
    version = (completed.stdout or completed.stderr).strip()
    return version or None


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )


def _run_passed(run: object) -> bool:
    has_passed = getattr(run, "has_passed", None)
    if callable(has_passed):
        return bool(has_passed())
    passed = getattr(run, "passed", None)
    if passed is not None:
        return bool(passed)
    return True


def _findings_from_run(run: object) -> List[Finding]:
    for attribute in ("findings", "errors", "checks"):
        value = getattr(run, attribute, None)
        findings = _findings_from_collection(value)
        if findings:
            return findings
    return []


def _findings_from_collection(value: object) -> List[Finding]:
    if not isinstance(value, list):
        return []
    findings = []
    for item in value:
        if isinstance(item, Finding):
            findings.append(item)
        elif isinstance(item, dict):
            findings.append(
                Finding(
                    code=str(item.get("code") or "DATACONTRACT_FINDING"),
                    message=str(item.get("message") or item),
                    severity=str(item.get("severity") or "error"),
                    path=_optional_str(item.get("path")),
                    source=TOOL_NAME,
                )
            )
        else:
            findings.append(
                Finding(
                    code="DATACONTRACT_FINDING",
                    message=str(item),
                    severity="error",
                    source=TOOL_NAME,
                )
            )
    return findings


def _findings_from_output(output: str, returncode: int) -> List[Finding]:
    if returncode == 0:
        return []
    if not output:
        return [
            Finding(
                code="DATACONTRACT_VALIDATION_FAILED",
                message="Data Contract validation failed.",
                severity="error",
                source=TOOL_NAME,
            )
        ]
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return [
            Finding(
                code="DATACONTRACT_VALIDATION_FAILED",
                message=output,
                severity="error",
                source=TOOL_NAME,
            )
        ]
    if isinstance(payload, dict):
        findings = _findings_from_collection(payload.get("findings"))
        if findings:
            return findings
        return [
            Finding(
                code=str(payload.get("code") or "DATACONTRACT_VALIDATION_FAILED"),
                message=str(payload.get("message") or payload),
                severity=str(payload.get("severity") or "error"),
                source=TOOL_NAME,
            )
        ]
    return [
        Finding(
            code="DATACONTRACT_VALIDATION_FAILED",
            message=str(payload),
            severity="error",
            source=TOOL_NAME,
        )
    ]


def _infer_contract_format(path_or_url: str) -> Optional[str]:
    suffix = Path(path_or_url).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    return None


def _optional_str(value: object) -> Optional[str]:
    return str(value) if value is not None else None
