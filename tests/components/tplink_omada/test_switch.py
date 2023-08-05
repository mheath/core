"""Tests for TP-Link Omada switch entities."""
from datetime import timedelta
import json
from unittest.mock import MagicMock

from tplink_omada_client.devices import OmadaSwitchPortDetails
from tplink_omada_client.omadasiteclient import SwitchPortOverrides

from homeassistant.components import switch
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


async def test_poe_switches(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test PoE switch."""
    poe_switch_mac = "54-AF-97-00-00-01"
    for i in range(1, 7):
        await _test_poe_switch(
            hass,
            mock_omada_site_client,
            f"switch.test_poe_switch_port_{i}_poe",
            poe_switch_mac,
            i,
        )


async def _test_poe_switch(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    entity_id: str,
    network_switch_mac: str,
    port: int,
) -> None:
    entity_registry = er.async_get(hass)

    port_id = f"{port:024}"

    def assert_update_switch_port(
        device, called_port, poe_enable: bool, overrides: SwitchPortOverrides
    ):
        assert device
        assert device.mac == network_switch_mac
        assert called_port
        assert called_port.port_id == port_id
        assert overrides
        assert overrides.enable_poe == poe_enable

        # return OmadaSwitchPortDetails({"poe": 1 if overrides.enable_poe else 0})

    entity = hass.states.get(entity_name)
    assert entity
    assert entity.state == "on"
    entry = entity_registry.async_get(entity_name)
    assert entry
    assert entry.unique_id == f"{network_switch_mac}_{port_id}_poe"

    mock_omada_site_client.update_switch_port.reset_mock()
    await call_service(hass, "turn_off", entity_name)
    mock_omada_site_client.update_switch_port.assert_called_once()
    device, switch_port = mock_omada_site_client.update_switch_port.call_args.args
    assert_update_switch_port(
        device,
        switch_port,
        False,
        **mock_omada_site_client.update_switch_port.call_args.kwargs,
    )
    await hass.async_block_till_done()
    entity = hass.states.get(entity_name)
    assert entity.state == "off"

    mock_omada_site_client.update_switch_port.reset_mock()
    await call_service(hass, "turn_on", entity_name)
    mock_omada_site_client.update_switch_port.assert_called_once()
    device, switch_port = mock_omada_site_client.update_switch_port.call_args.args
    assert_update_switch_port(
        device,
        switch_port,
        True,
        **mock_omada_site_client.update_switch_port.call_args.kwargs,
    )
    await hass.async_block_till_done()
    entity = hass.states.get(entity_name)
    assert entity.state == "on"


async def test_sfp_port_has_no_poe_switch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that a port that doesn't support SFTP isn't given a PoE switch entity."""
    entity = hass.states.get("switch.test_poe_switch_port_10_poe")
    assert entity is None


async def test_poe_default_port_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that a port with a default name is named correctly by the integration."""
    entity = hass.states.get("switch.test_poe_switch_port_2_poe")
    assert entity
    assert entity.name == "Test PoE Switch Port 2 PoE"


async def test_poe_custom_port_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that a port with a custom name is named correctly by the integration."""
    # Note: Port 8 has been renamed in the test fixture data
    entity = hass.states.get("switch.test_poe_switch_port_8_renamed_port_poe")
    assert entity
    assert entity.name == "Test PoE Switch Port 8 (Renamed Port) PoE"


async def test_poe_port_update_is_reflected_in_status(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that when the API is polled for an update, the changes are reflected in the switch state."""
    state = hass.states.get("switch.test_poe_switch_port_1_poe")
    assert state.state == "on"

    # Set up the API to return one of the ports as disabled
    mock_omada_site_client.get_switch_ports.reset_mock()
    switch1_ports_data = json.loads(
        load_fixture("switch-ports-TL-SG3210XHP-M2.json", DOMAIN)
    )
    switch1_ports_data[0]["poe"] = 0  # PoEMode.DISABLED
    switch1_ports = [OmadaSwitchPortDetails(p) for p in switch1_ports_data]
    mock_omada_site_client.get_switch_ports.return_value = switch1_ports

    # Cause the coordinator to refresh the data from the API
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=600))
    await hass.async_block_till_done()

    mock_omada_site_client.get_switch_ports.assert_called_once()
    state = hass.states.get("switch.test_poe_switch_port_1_poe")
    assert state.state == "off"


def call_service(hass, service, entity_id):
    """Call any service on entity."""
    return hass.services.async_call(
        switch.DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
