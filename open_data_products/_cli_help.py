"""Focused help for the guided configuration and delivery commands."""

import argparse
import textwrap


class TaskHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Present top-level commands in task-oriented groups."""

    def _format_action(self, action):
        if (
            not isinstance(action, argparse._SubParsersAction)
            or action.dest != "command"
        ):
            return super()._format_action(action)
        groups = {
            "Start and configure": [],
            "Data products and delivery": [],
            "Validate and inspect": [],
            "Catalogs, graphs and portfolios": [],
            "Other tools": [],
        }
        for choice in action._get_subactions():
            name = choice.dest
            if name in ("config", "connect"):
                group = "Start and configure"
            elif name in (
                "handover",
                "jira",
                "openmetadata",
                "generate",
                "product",
            ):
                group = "Data products and delivery"
            elif name in (
                "validate",
                "explain",
                "refs",
                "summary",
                "resources",
            ) or name.endswith("-validate"):
                group = "Validate and inspect"
            elif name.startswith(("odpc-", "odpg-", "odpv-")) or name in (
                "portfolio",
                "recipe",
            ):
                group = "Catalogs, graphs and portfolios"
            else:
                group = "Other tools"
            groups[group].append(choice)
        lines = []
        for title, choices in groups.items():
            if not choices:
                continue
            lines.append("  " + title + ":\n")
            for choice in choices:
                label = choice.metavar or choice.dest
                text = choice.help or ""
                wrapped = textwrap.wrap(text, width=max(20, self._width - 30)) or [""]
                lines.append("    {:<24} {}\n".format(label, wrapped[0]))
                for continuation in wrapped[1:]:
                    lines.append("    {:<24} {}\n".format("", continuation))
        return "".join(lines)


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
            description="Deliver a prepared handover to Jira Cloud. Human mode reviews interactively; agent mode creates issues without prompts. Requires JIRA_PROJECT and JIRA_ISSUE_TYPE_ID.",
            epilog="Examples: open-data-products jira deliver --input WORKSPACE; open-data-products jira deliver --input results.json --mode agent > jira-results.json. WORKSPACE is printed by handover prepare; inspect Jira before retrying an unknown outcome.",
        )
        parser.add_argument(
            "--input",
            required=True,
            metavar="WORKSPACE",
            help="Prepared workspace, folder of workspaces, or handover results JSON",
        )
        parser.add_argument(
            "--connections", help="Connection configuration (default: connections.yaml)"
        )
        parser.add_argument(
            "--connection", help="Named Jira connection (default: jira)"
        )
        parser.add_argument("--fields", help="JSON file of required Jira custom fields")
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit delivery results as JSON",
        )
        parser.add_argument(
            "--env-file", help="Environment file (default: local .env, if present)"
        )
        parser.add_argument(
            "--mode",
            choices=("human", "agent"),
            default="human",
            help="human: review interactively (default); agent: create issues without prompts and emit JSON",
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
        ): "Configure LLM, platform connections, or organization defaults with an interactive review.",
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
        ("llm", None): "Manage named LLM providers. Choose add, list, use or edit.",
        (
            "llm",
            "add",
        ): "Interactively add a built-in or custom provider without changing the active provider.",
        ("llm", "list"): "List built-in, configured and active LLM providers.",
        ("llm", "use"): "Review and select an existing configured LLM provider.",
        (
            "llm",
            "edit",
        ): "Review changes to an existing provider's model, endpoint or credential.",
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
        ("organization", None): "Show or edit default ODPS data holder details.",
        (
            "organization",
            "show",
        ): "Show organization defaults used in generated ODPS drafts.",
        (
            "organization",
            "edit",
        ): "Review and save organization details for generated ODPS drafts.",
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
        ("organization", None): "Change: open-data-products config organization edit",
        ("llm", "add"): "Next: open-data-products config llm use --name PROVIDER",
        ("connections", "add"): "Next: open-data-products config connections list",
    }
    parser = argparse.ArgumentParser(
        prog=command, description=description, epilog=examples.get((domain, leaf))
    )
    if (domain, leaf) in (
        ("llm", "use"),
        ("llm", "edit"),
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
        ("organization", "show"),
        ("organization", None),
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
