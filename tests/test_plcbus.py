"""Tests for PLCBUS UI configuration, migration, and lifecycle."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import voluptuous as vol

from custom_components.plcbus import async_setup_entry, async_unload_entry
from custom_components.plcbus.config_flow import PLCBusConfigFlow
from custom_components.plcbus.const import DOMAIN
from custom_components.plcbus.lib.plcbus_lib import PLCBUSException
from custom_components.plcbus.lib.PLCBusSerialHandler import serialHandler
from custom_components.plcbus import switch
from custom_components.plcbus.validation import normalize_config


def make_flow():
    flow = PLCBusConfigFlow()
    flow.context = {"source": "user"}
    flow.hass = MagicMock()
    flow.hass.config_entries.async_entries.return_value = []
    flow.hass.config_entries.flow.async_progress_by_handler.return_value = []
    flow.hass.config_entries.async_entry_for_domain_unique_id.return_value = None
    return flow


@pytest.mark.asyncio
async def test_user_form_and_creation():
    flow = make_flow()
    form = await flow.async_step_user()
    assert form["type"] == "form"
    assert form["data_schema"]({"user_code": "d1"}) == {
        "device": "", "user_code": "d1", "unit": ""
    }
    result = await flow.async_step_user(
        {"device": "/dev/ttyUSB0", "user_code": "d1", "unit": "a1,A1,b6"}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "device": "/dev/ttyUSB0", "user_code": "D1", "unit": ["A1", "B6"]
    }


@pytest.mark.asyncio
async def test_invalid_input_preserves_unit_text():
    flow = make_flow()
    result = await flow.async_step_user(
        {"device": "/dev/ttyUSB0", "user_code": "GG", "unit": "A1,B6"}
    )
    assert result["errors"] == {"base": "invalid_config"}
    assert result["data_schema"]({"user_code": "D1"})["unit"] == "A1,B6"


@pytest.mark.asyncio
async def test_auto_detection():
    flow = make_flow()
    flow.hass.async_add_executor_job = AsyncMock(return_value="/dev/ttyUSB1")
    result = await flow.async_step_user({"user_code": "D1"})
    assert result["data"]["device"] == "/dev/ttyUSB1"
    flow.hass.async_add_executor_job.assert_awaited_once()
    flow = make_flow()
    flow.hass.async_add_executor_job = AsyncMock(return_value=None)
    result = await flow.async_step_user({"user_code": "D1"})
    assert result["errors"] == {"base": "invalid_config"}


@pytest.mark.asyncio
async def test_yaml_import_and_single_instance():
    flow = make_flow()
    flow.context = {"source": "import"}
    result = await flow.async_step_import(
        {"device": "/dev/ttyUSB0", "user_code": "D1", "unit": ["A1"]}
    )
    assert result["type"] == "create_entry"
    flow.hass.config_entries.async_entries.return_value = [MagicMock()]
    result = await flow.async_step_import({"user_code": "D1"})
    assert result["reason"] == "single_instance_allowed"
    result = await flow.async_step_user()
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.asyncio
async def test_reconfigure():
    flow = make_flow()
    entry = SimpleNamespace(data={
        "device": "/dev/ttyUSB0", "user_code": "D1", "unit": ["A1"]
    })
    with (
        patch.object(flow, "_get_reconfigure_entry", return_value=entry),
        patch.object(flow, "async_update_reload_and_abort", return_value={"type": "abort"}) as reload,
    ):
        form = await flow.async_step_reconfigure()
        assert form["data_schema"]({})["unit"] == "A1"
        await flow.async_step_reconfigure(
            {"device": "/dev/ttyUSB1", "user_code": "d1", "unit": "b6"}
        )
        reload.assert_called_once_with(entry, data_updates={
            "device": "/dev/ttyUSB1", "user_code": "D1", "unit": ["B6"]
        })


@pytest.mark.parametrize("config", [
    {"user_code": "D1x"},
    {"user_code": "D1", "unit": "Q1"},
    {"user_code": "D1", "unit": "A17"},
    {"user_code": "D1", "unit": ["A1", 2]},
])
def test_invalid_configuration(config):
    with pytest.raises(vol.Invalid):
        normalize_config(config)


def test_yaml_only_schedules_import():
    hass = MagicMock()
    switch.setup_platform(hass, {"user_code": "D1"}, MagicMock())
    hass.config_entries.flow.async_init.assert_called_once_with(
        DOMAIN, context={"source": "import"}, data={"user_code": "D1"}
    )
    hass.add_job.assert_called_once()


@pytest.mark.asyncio
async def test_forward_platform():
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock()
    assert await async_setup_entry(hass, entry)
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()


@pytest.mark.asyncio
async def test_switch_setup_polling_shutdown_and_late_messages():
    hass = MagicMock()
    hass.data = {}
    entry = SimpleNamespace(
        entry_id="entry", data={
            "device": "/dev/ttyUSB0", "user_code": "D1", "unit": ["A1"]
        }
    )
    jobs = []
    hass.add_job.side_effect = lambda func, *args: jobs.append((func, args))

    async def executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = executor
    api = MagicMock()
    add_entities = MagicMock()
    cancel_poll = MagicMock()
    cancel_stop = MagicMock()
    hass.bus.async_listen_once.return_value = cancel_stop
    with (
        patch.object(switch, "PLCBUSAPI", return_value=api) as factory,
        patch.object(switch, "async_track_time_interval", return_value=cancel_poll) as tracker,
    ):
        await switch.async_setup_entry(hass, entry, add_entities)
        while jobs:
            func, args = jobs.pop(0)
            func(*args)
        entity = hass.data[DOMAIN]["entry"]["switches"][0]
        assert entity.unique_id == "PlcbusSwitch_D1_A1"
        api.send.assert_any_call("GET_ALL_ID_PULSE", "A", "D1")
        poll = tracker.call_args.args[1]
        poll()
        api.send.assert_any_call("GET_ALL_ON_ID_PULSE", "A", "D1")
        callback = factory.call_args.args[2]
        callback({"d_command": "STATUS_ON", "d_home_unit": "A1"})
        while jobs:
            func, args = jobs.pop(0)
            func(*args)
        assert entity.is_on is True
        entity.turn_off()
        assert entity.is_on is True
        api.send.assert_any_call("OFF", "A1", "D1")
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        shutdown = hass.data[DOMAIN]["entry"]["shutdown"]
        assert await async_unload_entry(hass, entry)
        await shutdown()
        cancel_poll.assert_called_once()
        cancel_stop.assert_called_once()
        api.stop.assert_called_once()
        callback({"d_command": "STATUS_OFF", "d_home_unit": "A1"})
        while jobs:
            func, args = jobs.pop(0)
            func(*args)
        assert entity.is_on is True
        assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_failed_setup_retries():
    hass = MagicMock()
    hass.data = {}
    entry = SimpleNamespace(entry_id="entry", data={})
    hass.async_add_executor_job = AsyncMock(side_effect=PLCBUSException("Cannot open"))
    with pytest.raises(ConfigEntryNotReady):
        await switch.async_setup_entry(hass, entry, MagicMock())
    assert hass.data[DOMAIN] == {}


@pytest.mark.asyncio
async def test_failed_platform_unload_keeps_connection():
    stop = AsyncMock()
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": {"shutdown": stop}}}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    assert not await async_unload_entry(hass, SimpleNamespace(entry_id="entry"))
    stop.assert_not_awaited()
    assert "entry" in hass.data[DOMAIN]


def test_translations():
    root = Path(__file__).parents[1] / "custom_components/plcbus"
    source = json.loads((root / "strings.json").read_text())
    assert json.loads((root / "translations/en.json").read_text()) == source
    spanish = json.loads((root / "translations/es.json").read_text())
    for section in ("step", "error", "abort"):
        assert spanish["config"][section].keys() == source["config"][section].keys()


def test_serial_thread_stops_and_joins():
    serial = MagicMock()
    serial.in_waiting = 0
    with patch(
        "custom_components.plcbus.lib.PLCBusSerialHandler.serial.Serial",
        return_value=serial,
    ):
        handler = serialHandler("/dev/ttyUSB0", MagicMock(), MagicMock())
        handler.start()
        handler.stop()
        handler.join(timeout=2)
        assert not handler.is_alive()
        serial.close.assert_called_once()


@pytest.mark.asyncio
async def test_real_home_assistant_event_loop(tmp_path):
    """Exercise actual thread-safe scheduling, discovery, and event cancellation."""
    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(entry_id="entry", data={
        "device": "/dev/ttyUSB0", "user_code": "D1", "unit": ["A1"]
    })
    entities = []

    @callback
    def add_entities(new_entities, update_before_add=False):
        entities.extend(new_entities)

    api = MagicMock()

    def create_api(log, device, command, message):
        command({"d_command": "STATUS_ON", "d_home_unit": "A1"})
        return api

    try:
        with patch.object(switch, "PLCBUSAPI", side_effect=create_api) as factory:
            await switch.async_setup_entry(hass, entry, add_entities)
            await hass.async_block_till_done()
            assert len(entities) == 1
            assert entities[0].is_on is True
            command = factory.call_args.args[2]
            await hass.async_add_executor_job(command, {
                "d_command": "GET_ALL_ID_PULSE", "d_home_unit": "B1",
                "d_data1": 0, "d_data2": 1,
            })
            await hass.async_block_till_done()
            assert [entity.unit_code for entity in entities] == ["A1", "B1"]
            await hass.data[DOMAIN][entry.entry_id]["shutdown"]()
            await hass.async_block_till_done()
            api.stop.assert_called_once()
    finally:
        await hass.async_stop(force=True)
