"""Integration tests for ha_call_service / ha_list_services against real HA.

Registers real services (with real SupportsResponse flags) and drives them
through the handlers, covering the return_response auto-detection that a mock
can't exercise.
"""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools.services import ha_call_service, ha_list_services

_DOMAIN = "hmcp_test"


@pytest.fixture
def registered(hass: HomeAssistant):
    calls: list[dict] = []

    async def act(call: ServiceCall):
        calls.append(dict(call.data))

    async def respond(call: ServiceCall):
        return {"pong": call.data.get("ping")}

    hass.services.async_register(_DOMAIN, "act", act)
    hass.services.async_register(
        _DOMAIN, "respond", respond, supports_response=SupportsResponse.OPTIONAL
    )
    return calls


@pytest.mark.asyncio
async def test_autodetects_response_for_optional_service(hass, registered) -> None:
    result = await ha_call_service(hass, _DOMAIN, "respond", service_data={"ping": 5})
    assert result["called"] is True
    assert result["return_response"] is True
    assert result["response"] == {"pong": 5}


@pytest.mark.asyncio
async def test_no_response_for_plain_service(hass, registered) -> None:
    result = await ha_call_service(hass, _DOMAIN, "act", service_data={"x": 1})
    assert result["called"] is True
    assert result["return_response"] is False
    assert result["response"] is None
    assert registered == [{"x": 1}]


@pytest.mark.asyncio
async def test_forcing_response_on_none_service_errors(hass, registered) -> None:
    with pytest.raises(ToolError):
        await ha_call_service(hass, _DOMAIN, "act", return_response=True)


@pytest.mark.asyncio
async def test_unknown_service_errors(hass, registered) -> None:
    with pytest.raises(ToolError):
        await ha_call_service(hass, _DOMAIN, "does_not_exist")


@pytest.mark.asyncio
async def test_list_services_reports_supports_response(hass, registered) -> None:
    result = await ha_list_services(hass, domain=_DOMAIN)
    by_id = {i["id"]: i for i in result["items"]}
    assert by_id["hmcp_test.respond"]["supports_response"] == "optional"
    assert by_id["hmcp_test.act"]["supports_response"] == "none"
