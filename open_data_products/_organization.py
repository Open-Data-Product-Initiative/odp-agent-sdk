"""Project-local default data holder for ODPS drafts."""

import json
from pathlib import Path
import re

import jsonschema
import yaml

from .integrations.config import _UniqueLoader

PATH = Path(".open-data-products/organization.yaml")
FIELDS = (
    "legalName",
    "businessID",
    "contactName",
    "email",
    "taxID",
    "vatID",
    "businessDomain",
    "logoURL",
    "description",
    "URL",
    "telephone",
    "streetAddress",
    "postalCode",
    "addressRegion",
    "addressLocality",
    "addressCountry",
    "aggregateRating",
    "ratingCount",
    "slogan",
    "parentOrganization",
)


def validate_organization(config):
    """Validate configured details against both bundled ODPS schemas."""
    if (
        not isinstance(config, dict)
        or set(config) != {"version", "language", "dataHolder"}
        or config["version"] != 1
    ):
        raise ValueError(
            "Organization configuration requires version 1, language and dataHolder"
        )
    language = config["language"]
    if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2}", language):
        raise ValueError("Organization language must be a two-letter lowercase code")
    holder = config["dataHolder"]
    if not isinstance(holder, dict) or set(holder) - set(FIELDS):
        raise ValueError("Organization contains unsupported data holder fields")
    if not isinstance(holder.get("legalName"), str) or not holder["legalName"].strip():
        raise ValueError("Organization legalName is required")
    if any(
        isinstance(v, str)
        and (not v.strip() or any(ord(c) < 32 or ord(c) == 127 for c in v))
        for v in holder.values()
    ):
        raise ValueError(
            "Organization details must not be empty or contain control characters"
        )
    root = Path(__file__).parent / "odps" / "data" / "schema"
    for version, definition in (("4.1", "DataHolder"), ("4.2", "DataHolderDetails")):
        schema = json.loads(
            (root / ("odps-v" + version + ".json")).read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(
            {"$ref": "#/$defs/" + definition, "$defs": schema["$defs"]},
            format_checker=jsonschema.FormatChecker(),
        )
        errors = list(validator.iter_errors(holder))
        if errors:
            field = ".".join(str(p) for p in errors[0].path) or "dataHolder"
            raise ValueError(
                "Invalid organization field for ODPS " + version + ": " + field
            )
    from .odps._validators import ODPSValidator

    for field, check in (
        ("email", ODPSValidator.validate_email),
        ("URL", ODPSValidator.validate_url),
        ("addressCountry", ODPSValidator.validate_country_code),
    ):
        if field in holder and not check(holder[field]):
            raise ValueError("Invalid organization field: " + field)
    return config


def load_organization():
    """Read the optional project default without following symbolic links."""
    if PATH.parent.is_symlink() or PATH.is_symlink():
        raise ValueError("Organization configuration cannot use symbolic links")
    if not PATH.exists():
        return None
    if not PATH.is_file() or PATH.stat().st_size > 1024 * 1024:
        raise ValueError(
            "Organization configuration must be a regular file at most 1 MiB"
        )
    try:
        config = yaml.load(PATH.read_text(encoding="utf-8"), Loader=_UniqueLoader)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ValueError("Cannot read organization configuration") from None
    return validate_organization(config)


def apply_organization(document, config):
    """Apply absent defaults without replacing an existing or conflicting holder."""
    if not config:
        return []
    validate_organization(config)
    product = document.get("product")
    if not isinstance(product, dict):
        return ["Configured data holder was not applied: product is missing."]
    version = str(document.get("version", ""))
    if version not in ("4.1", "4.2"):
        return ["Configured data holder was not applied: unsupported ODPS version."]
    default = config["dataHolder"]
    existing = product.get("dataHolder")
    if existing is None:
        product["dataHolder"] = (
            dict(default) if version == "4.1" else {config["language"]: dict(default)}
        )
        return [
            "Configured organization default applied to dataHolder: "
            + ", ".join(default)
            + ". Review ownership."
        ]
    if not isinstance(existing, dict):
        return [
            "Configured data holder was not applied: existing dataHolder is invalid."
        ]
    if version == "4.2":
        for item in existing.values():
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("legalName"), str)
                or item["legalName"].strip().casefold()
                != default["legalName"].strip().casefold()
            ):
                return [
                    "Configured data holder was not applied: existing organization differs or is incomplete; review ownership."
                ]
        holder = existing.setdefault(config["language"], {})
    else:
        holder = existing
    if holder and (
        not isinstance(holder.get("legalName"), str)
        or holder["legalName"].strip().casefold()
        != default["legalName"].strip().casefold()
    ):
        return [
            "Configured data holder was not applied: existing organization differs or is incomplete; review ownership."
        ]
    added, conflicts = [], []
    for key, value in default.items():
        if key not in holder:
            holder[key] = value
            added.append(key)
        elif holder[key] != value:
            conflicts.append(key)
    notes = []
    if added:
        notes.append(
            "Configured organization defaults applied to dataHolder: "
            + ", ".join(added)
            + ". Review ownership."
        )
    if conflicts:
        notes.append(
            "Configured organization conflicts with existing dataHolder fields: "
            + ", ".join(conflicts)
            + "; existing values retained."
        )
    return notes


def edit_organization():
    """Review and save project organization defaults interactively."""
    import sys
    from ._config_setup import _read, _write

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Organization setup requires an interactive terminal")
    current = load_organization() or {"version": 1, "language": "en", "dataHolder": {}}
    previous = _read(PATH)
    holder = dict(current["dataHolder"])
    print(
        "Organization defaults populate ODPS dataHolder. Existing conflicting values are preserved."
    )
    print("Leave blank to keep a value; enter - to remove an optional value.")
    print(
        "These details become part of generated specs and may be shared with a provider in later workflows."
    )
    language = (
        input("Language [" + current["language"] + "]: ").strip() or current["language"]
    )
    basic = (
        "legalName",
        "businessID",
        "contactName",
        "email",
        "URL",
        "businessDomain",
        "description",
    )

    def collect(fields):
        for field in fields:
            old = holder.get(field)
            value = input(
                field + (" [" + str(old) + "]" if old is not None else "") + ": "
            ).strip()
            if value == "-" and field != "legalName":
                holder.pop(field, None)
            elif value:
                if field == "ratingCount":
                    try:
                        value = int(value)
                    except ValueError:
                        raise ValueError("ratingCount must be an integer") from None
                holder[field] = value

    collect(basic)
    if input("Edit additional ODPS organization details? [y/N]: ").strip().lower() in (
        "y",
        "yes",
    ):
        collect([f for f in FIELDS if f not in basic])
    config = validate_organization(
        {"version": 1, "language": language, "dataHolder": holder}
    )
    print(
        "Review organization defaults:\n"
        + yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
    )
    if input("Save these settings? [y/N]: ").strip().lower() not in ("y", "yes"):
        print("No organization settings changed.")
        return 0
    if PATH.parent.is_symlink():
        raise ValueError("Organization configuration cannot use symbolic links")
    PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _write(
        PATH,
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True).encode(),
        previous,
    )
    PATH.chmod(0o600)
    print(
        "Organization defaults saved. Change them with: open-data-products config organization edit"
    )
    return 0


def show_organization(as_json=False):
    """Show project organization defaults."""
    config = load_organization()
    if as_json:
        print(json.dumps(config or {}, indent=2, ensure_ascii=False))
    else:
        print(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
            if config
            else "Organization: not configured"
        )
        print("Change: open-data-products config organization edit")
    return 0
