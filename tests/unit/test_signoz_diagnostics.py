from traceforge.signoz import _connection_error


def test_mcp_bad_instance_url_is_classified_without_echoing_it() -> None:
    private_host = "private.example.signoz.cloud"
    failure = ExceptionGroup(
        "transport",
        [RuntimeError(f'HTTP 400: Invalid X-SigNoz-URL "{private_host}"')],
    )

    message = _connection_error(failure)

    assert "configuration rejected X-SigNoz-URL" in message
    assert private_host not in message


def test_mcp_auth_and_permission_failures_are_distinct() -> None:
    assert "authentication failed" in _connection_error(RuntimeError("HTTP 401"))
    assert "permission denied" in _connection_error(RuntimeError("HTTP 403"))
