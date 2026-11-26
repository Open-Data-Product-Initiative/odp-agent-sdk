"""Offline tests for general Jira issue requests."""

import pytest

from open_data_products.integrations.config import IntegrationError
from open_data_products.integrations.jira import (
    JiraCloudAdapter,
    JiraConnection,
    JiraIssueRequest,
)


def test_general_issue_review_and_create(monkeypatch):
    adapter = JiraCloudAdapter(
        JiraConnection(
            "team", "https://example.atlassian.net", "EMAIL", "TOKEN", read_only=False
        )
    )
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET":
            return {"values": [{"fieldId": "customfield_10000", "required": True}]}
        return {"key": "DATA-1"}

    monkeypatch.setattr(adapter, "_request", request)
    issue = JiraIssueRequest(
        "DATA",
        "10000",
        "Example",
        "# Context\n\n- Read [source](https://example.org/doc)",
        {"customfield_10000": "ready"},
    )
    review = adapter.review_issue(issue)
    assert all(call[0] == "GET" for call in calls)
    assert review["payload"]["fields"]["description"]["content"][0]["type"] == "heading"
    with pytest.raises(IntegrationError, match="changed"):
        adapter.create_issue(
            JiraIssueRequest(
                "DATA", "10000", "Changed", issue.description, issue.fields
            ),
            reviewed_sha256=review["reviewed_sha256"],
        )
    assert all(call[0] == "GET" for call in calls)
    result = adapter.create_issue(issue, reviewed_sha256=review["reviewed_sha256"])
    assert result["key"] == "DATA-1"
    assert sum(call[0] == "POST" for call in calls) == 1


def test_required_custom_field(monkeypatch):
    adapter = JiraCloudAdapter(
        JiraConnection("team", "https://example.atlassian.net", "EMAIL", "TOKEN")
    )
    monkeypatch.setattr(
        adapter,
        "_request",
        lambda *args: {"values": [{"fieldId": "customfield_7", "required": True}]},
    )
    with pytest.raises(IntegrationError, match="customfield_7"):
        adapter.review_issue(JiraIssueRequest("DATA", "10", "Title", "Text"))


def test_jira_cloud_create_metadata_fields_response(monkeypatch):
    adapter = JiraCloudAdapter(
        JiraConnection("team", "https://example.atlassian.net", "EMAIL", "TOKEN")
    )

    def request(method, path, body=None):
        if path.startswith("issue/createmeta/"):
            return {
                "startAt": 0,
                "maxResults": 50,
                "total": 3,
                "fields": [
                    {"fieldId": "project", "required": True},
                    {"fieldId": "summary", "required": True},
                    {"fieldId": "reporter", "required": True, "hasDefaultValue": True},
                ],
            }
        return {"issues": []}

    monkeypatch.setattr(adapter, "_request", request)
    review = adapter.review_issue(JiraIssueRequest("SCRUM", "10003", "Title", "Text"))
    assert review["payload"]["fields"]["project"] == {"key": "SCRUM"}


def test_attachment_review_and_partial_failure(tmp_path, monkeypatch):
    adapter = JiraCloudAdapter(
        JiraConnection(
            "team", "https://example.atlassian.net", "EMAIL", "TOKEN", read_only=False
        )
    )
    monkeypatch.setattr(
        adapter,
        "_request",
        lambda method, *args: (
            {"values": [{"fieldId": "summary", "required": True}]}
            if method == "GET"
            else {"key": "DATA-5"}
        ),
    )
    file = tmp_path / "brief.txt"
    file.write_text("first")
    issue = JiraIssueRequest("DATA", "10", "Title", "Text", attachments=(str(file),))
    review = adapter.review_issue(issue)
    file.write_text("changed")
    with pytest.raises(IntegrationError, match="changed"):
        adapter.create_issue(issue, reviewed_sha256=review["reviewed_sha256"])
    review = adapter.review_issue(issue)

    def failed_upload(*args):
        raise IntegrationError("Unavailable")

    monkeypatch.setattr(adapter, "_upload_attachment", failed_upload)
    result = adapter.create_issue(issue, reviewed_sha256=review["reviewed_sha256"])
    assert result["key"] == "DATA-5"
    assert result["attachment_failures"] == ["brief.txt"]


def test_named_connection_uses_environment_references(tmp_path):
    from open_data_products.integrations.jira import load_jira_connection

    config = tmp_path / "connections.yaml"
    config.write_text("""version: 1
default_connection: jira
connections:
  jira:
    platform: jira_cloud
    base_url: https://example.atlassian.net
    read_only: false
    auth:
      type: basic_env
      email_env: JIRA_EMAIL
      token_env: JIRA_TOKEN
""")
    connection = load_jira_connection(config)
    assert connection.name == "jira"
    assert connection.email_env == "JIRA_EMAIL"
    assert connection.token_env == "JIRA_TOKEN"
    assert connection.read_only is False


@pytest.mark.parametrize("failure", ["timeout", "incomplete_response"])
def test_post_timeout_is_unknown_and_not_retried(monkeypatch, failure):
    from http.client import IncompleteRead
    from urllib.error import URLError
    from open_data_products.integrations.jira import JiraUnknownOutcome

    adapter = JiraCloudAdapter(
        JiraConnection(
            "team", "https://example.atlassian.net", "EMAIL", "TOKEN", read_only=False
        )
    )
    monkeypatch.setenv("EMAIL", "user@example.org")
    monkeypatch.setenv("TOKEN", "fake-token")
    calls = []

    def fail(request, timeout):
        calls.append(request.method)
        if failure == "incomplete_response":
            raise IncompleteRead(b"")
        raise URLError("timeout")

    monkeypatch.setattr(adapter._opener, "open", fail)
    with pytest.raises(JiraUnknownOutcome, match="unknown"):
        adapter._request("POST", "issue", {"fields": {}})
    assert calls == ["POST"]


@pytest.mark.parametrize("status", [302, 408, 500, 503])
def test_uncertain_http_creation_response_is_unknown(monkeypatch, status):
    from urllib.error import HTTPError
    from open_data_products.integrations.jira import JiraUnknownOutcome

    adapter = JiraCloudAdapter(
        JiraConnection("team", "https://example.atlassian.net", "EMAIL", "TOKEN")
    )
    monkeypatch.setenv("EMAIL", "user@example.org")
    monkeypatch.setenv("TOKEN", "fake-token")
    calls = []

    def fail(request, timeout):
        calls.append(request.method)
        raise HTTPError(request.full_url, status, "failure", {}, None)

    monkeypatch.setattr(adapter._opener, "open", fail)
    with pytest.raises(JiraUnknownOutcome, match="unknown"):
        adapter._request("POST", "issue", {"fields": {}})
    assert calls == ["POST"]


def test_nonobject_creation_response_is_unknown(monkeypatch):
    from io import BytesIO
    from open_data_products.integrations.jira import JiraUnknownOutcome

    adapter = JiraCloudAdapter(
        JiraConnection("team", "https://example.atlassian.net", "EMAIL", "TOKEN")
    )
    monkeypatch.setenv("EMAIL", "user@example.org")
    monkeypatch.setenv("TOKEN", "fake-token")
    monkeypatch.setattr(adapter._opener, "open", lambda *args, **kwargs: BytesIO(b"[]"))
    with pytest.raises(JiraUnknownOutcome, match="unknown"):
        adapter._request("POST", "issue", {"fields": {}})


def test_markdown_to_adf_preserves_order_and_links():
    from open_data_products.integrations.jira import markdown_to_adf

    result = markdown_to_adf(
        "# Title\n\n1. Read [source](https://example.org/doc)\n2. Review"
    )
    assert [x["type"] for x in result["content"]] == ["heading", "orderedList"]
    assert (
        result["content"][1]["content"][0]["content"][0]["content"][1]["marks"][0][
            "attrs"
        ]["href"]
        == "https://example.org/doc"
    )


def test_attachment_read_is_bounded(tmp_path):
    from open_data_products.integrations.jira import _read_attachment

    path = tmp_path / "large.zip"
    with path.open("wb") as handle:
        handle.truncate(10 * 1024 * 1024 + 2)
    with pytest.raises(IntegrationError, match="10 MiB"):
        _read_attachment(path)
