import httpx
import pytest

from services.dispatch.src.clients import DownstreamError, DownstreamTimeout, ServiceClients


@pytest.mark.parametrize("content", [b"not-json", b"[]", b"null"])
def test_invalid_downstream_response_is_a_retryable_gateway_error(monkeypatch, content):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(200, content=content))
    clients = ServiceClients("http://orders", "http://workforce", "http://notifications", 1)
    with pytest.raises(DownstreamError) as error:
        clients.notify({}, "correlation")
    assert error.value.status_code == 502
    assert error.value.body["error"]["code"] == "INVALID_DOWNSTREAM_RESPONSE"


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError])
def test_transport_failures_have_an_unknown_downstream_outcome(monkeypatch, error_type):
    def fail(*args, **kwargs):
        raise error_type("connection lost")

    monkeypatch.setattr(httpx, "post", fail)
    clients = ServiceClients("http://orders", "http://workforce", "http://notifications", 1)
    with pytest.raises(DownstreamTimeout) as error:
        clients.reserve({}, "correlation")
    assert error.value.service == "workforce"
