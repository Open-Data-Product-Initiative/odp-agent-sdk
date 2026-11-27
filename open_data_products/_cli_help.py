"""Focused help for the guided configuration and delivery commands."""

import argparse


def show_focused_help(argv):
    """Show command-specific help when requested, without changing parsing."""
    if "--help" not in argv and "-h" not in argv:
        return False
    path = []
    for value in argv:
        if value.startswith("-"):
            break
        path.append(value)
    if len(path) >= 2 and path[:2] == ["jira", "deliver"]:
        parser = argparse.ArgumentParser(
            prog="open-data-products jira deliver",
            description="Review a prepared handover and deliver it to Jira Cloud. Requires an interactive terminal, JIRA_PROJECT and JIRA_ISSUE_TYPE_ID.",
            epilog="Example: open-data-products jira deliver --input WORKSPACE. WORKSPACE is printed by handover prepare. If the outcome is unknown, inspect Jira before retrying.",
        )
        parser.add_argument(
            "--input",
            required=True,
            metavar="WORKSPACE",
            help="Workspace returned by handover prepare",
        )
        parser.add_argument(
            "--connections", help="Connection configuration (default: connections.yaml)"
        )
        parser.add_argument(
            "--connection", help="Named Jira connection (default: jira)"
        )
        parser.add_argument("--fields", help="JSON file of required Jira custom fields")
        parser.add_argument(
            "--env-file", help="Environment file (default: local .env, if present)"
        )
        parser.print_help()
        return True
    if len(path) < 2 or path[0] != "config":
        return False
    domain = path[1]
    leaf = path[2] if len(path) > 2 else None
    descriptions = {
        (
            "setup",
            None,
        ): "Configure an LLM, OpenMetadata, Jira, or all three with an interactive review.",
        (
            "show",
            None,
        ): "Show current settings and credential presence without printing secret values.",
        (
            "status",
            None,
        ): "Show current settings and credential presence without printing secret values.",
        (
            "test",
            None,
        ): "Test the configured LLM, OpenMetadata and Jira. The LLM test sends a short prompt and may incur cost; platform checks are read-only.",
        ("llm", None): "Manage named LLM providers. Choose add, list or use.",
        (
            "llm",
            "add",
        ): "Interactively add a built-in or custom provider without changing the active provider.",
        ("llm", "list"): "List built-in, configured and active LLM providers.",
        ("llm", "use"): "Review and select an existing configured LLM provider.",
        (
            "connections",
            None,
        ): "Manage named platform connections. Choose add, list or edit.",
        (
            "connections",
            "add",
        ): "Interactively add a named OpenMetadata or Jira Cloud connection.",
        (
            "connections",
            "list",
        ): "List named connections without resolving credentials.",
        ("connections", "edit"): "Review changes to an existing named connection.",
        ("credentials", None): "Store a credential securely using the set operation.",
        (
            "credentials",
            "set",
        ): "Enter a credential at a hidden prompt and review before saving it to .env.",
    }
    description = descriptions.get((domain, leaf))
    if description is None:
        return False
    command = "open-data-products " + " ".join(path)
    examples = {
        ("llm", None): "Next: open-data-products config llm add",
        ("connections", None): "Next: open-data-products config connections add",
        (
            "credentials",
            None,
        ): "Next: open-data-products config credentials set --name OPENAI_API_KEY",
        ("setup", None): "Next: open-data-products config show",
        ("llm", "add"): "Next: open-data-products config llm use --name PROVIDER",
        ("connections", "add"): "Next: open-data-products config connections list",
    }
    parser = argparse.ArgumentParser(
        prog=command, description=description, epilog=examples.get((domain, leaf))
    )
    if (domain, leaf) in (
        ("llm", "use"),
        ("connections", "edit"),
        ("credentials", "set"),
    ):
        parser.add_argument(
            "--name",
            required=True,
            help="Provider, connection or environment variable name",
        )
    if (domain, leaf) in (
        ("llm", "list"),
        ("connections", "list"),
        ("show", None),
        ("status", None),
        ("test", None),
    ):
        parser.add_argument("--json", action="store_true", help="Emit structured JSON")
    if domain in ("show", "status") and leaf is None:
        parser.add_argument(
            "--test",
            action="store_true",
            help="Test platform connectivity using read-only requests",
        )
    parser.print_help()
    return True
