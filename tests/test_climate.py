#
#    Copyright 2022-2024 Joe Block <jpb@unixorn.net>
#    Copyright 2024 Lucio Tarantino <lucio.tarantino@gmail.com>
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
import logging
from queue import Queue

# from threading import Event
from typing import Any, Callable, TypeVar
import pytest
from ha_mqtt_discoverable.climate import (
    Climate,
    ClimateInfo,
    ClimateSetting,
)
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish

messages_received: dict[str, Queue] = {}


@pytest.fixture(
    params=[
        dict(
            name="test1",
            manual_availability=True,
            capability=ClimateSetting.Capability.ACTION,
        ),
        dict(
            name="test2",
            manual_availability=False,
            capability=ClimateSetting.Capability.CURRENT_TEMPERATURE
            | ClimateSetting.Capability.TARGET_TEMPERATURE,
        ),
        dict(
            name="test3",
            manual_availability=False,
            capability=ClimateSetting.Capability.SWING_MODE
            | ClimateSetting.Capability.TARGET_HIGH_TEMPERATURE
            | ClimateSetting.Capability.TARGET_LOW_TEMPERATURE,
        ),
        dict(
            name="test4",
            manual_availability=False,
            capability=ClimateSetting.Capability.TARGET_HUMIDITY
            | ClimateSetting.Capability.MODE,
        ),
        dict(
            name="test5",
            manual_availability=False,
            capability=ClimateSetting.Capability.FAN_MODE
            | ClimateSetting.Capability.POWER,
        ),
        dict(
            name="test6",
            manual_availability=False,
            capability=ClimateSetting.Capability.PRESET_MODE,
        ),
    ]
)
def climate(request: pytest.FixtureRequest) -> Climate:
    mqtt_settings = ClimateSetting.MQTT(host="localhost")
    climate_info = ClimateInfo(
        name=request.param["name"], temperature_unit="C", preset_modes=["eco", "boost"]
    )
    settings = ClimateSetting(
        mqtt=mqtt_settings,
        entity=climate_info,
        manual_availability=request.param["manual_availability"],
        capability=request.param["capability"],
    )
    # Define empty callback
    T = TypeVar("T")  # Used in the callback function
    callbacks: dict[str, Callable[[mqtt.Client, T, mqtt.MQTTMessage], Any]] = {}

    # Callback to receive the command message
    def custom_callback(
        message_received: Queue, client, user_data, message: mqtt.MQTTMessage
    ):
        payload = message.payload.decode()
        logging.info(f"Received {payload} {user_data}")
        # assert payload == "on"
        # assert user_data == custom_user_data
        message_received.put(payload)

    if ClimateSetting.Capability.FAN_MODE in request.param["capability"]:
        messages_received["fan_mode_command_topic"] = Queue()
        callbacks["fan_mode_command_topic"] = lambda *_: custom_callback(
            messages_received["fan_mode_command_topic"], *_
        )
    if ClimateSetting.Capability.MODE in request.param["capability"]:
        messages_received["mode_command_topic"] = Queue()
        callbacks["mode_command_topic"] = lambda *_: custom_callback(
            messages_received["mode_command_topic"], *_
        )
    if ClimateSetting.Capability.POWER in request.param["capability"]:
        messages_received["power_command_topic"] = Queue()
        callbacks["power_command_topic"] = lambda *_: custom_callback(
            messages_received["power_command_topic"], *_
        )
    if ClimateSetting.Capability.PRESET_MODE in request.param["capability"]:
        messages_received["preset_mode_command_topic"] = Queue()
        callbacks["preset_mode_command_topic"] = lambda *_: custom_callback(
            messages_received["preset_mode_command_topic"], *_
        )
    if ClimateSetting.Capability.SWING_MODE in request.param["capability"]:
        messages_received["swing_mode_command_topic"] = Queue()
        callbacks["swing_mode_command_topic"] = lambda *_: custom_callback(
            messages_received["swing_mode_command_topic"], *_
        )
    if ClimateSetting.Capability.TARGET_HUMIDITY in request.param["capability"]:
        messages_received["target_humidity_command_topic"] = Queue()
        callbacks["target_humidity_command_topic"] = lambda *_: custom_callback(
            messages_received["target_humidity_command_topic"], *_
        )
    if ClimateSetting.Capability.TARGET_HIGH_TEMPERATURE in request.param["capability"]:
        messages_received["temperature_high_command_topic"] = Queue()
        callbacks["temperature_high_command_topic"] = lambda *_: custom_callback(
            messages_received["temperature_high_command_topic"], *_
        )
    if ClimateSetting.Capability.TARGET_LOW_TEMPERATURE in request.param["capability"]:
        messages_received["temperature_low_command_topic"] = Queue()
        callbacks["temperature_low_command_topic"] = lambda *_: custom_callback(
            messages_received["temperature_low_command_topic"], *_
        )
    if ClimateSetting.Capability.TARGET_TEMPERATURE in request.param["capability"]:
        messages_received["temperature_command_topic"] = Queue()
        callbacks["temperature_command_topic"] = lambda *_: custom_callback(
            messages_received["temperature_command_topic"], *_
        )

    return Climate(settings, callbacks)


def test_required_config():
    mqtt_settings = ClimateSetting.MQTT(host="localhost")
    climate_info = ClimateInfo(name="test")
    settings = ClimateSetting(mqtt=mqtt_settings, entity=climate_info)
    # Define empty callback
    text = Climate(settings, {"dump": lambda *_: None})
    assert text is not None


def test_generate_config(climate: Climate):
    config = climate.generate_config()

    assert config is not None
    # If we have defined a custom unit of measurement, check that is part of the
    # output config
    assert config["temperature_unit"] == climate._entity.temperature_unit


def test_update_avability(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if not climate._settings.manual_availability:
        pytest.skip()
    climate.set_availability(True)


def test_action(climate: Climate, request: pytest.FixtureRequest):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.ACTION not in climate._settings.capability:
        pytest.skip()
    climate.set_action(Climate.Action.OFF)
    # assert messages_received["action_topic"].wait(20)


def test_set_target_humidity(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.TARGET_HUMIDITY not in climate._settings.capability:
        pytest.skip()
    climate.set_target_humidity(30)


def test_command_target_humidity(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.TARGET_HUMIDITY not in climate._settings.capability:
        pytest.skip()

    publish.single(
        climate._command_topics["target_humidity_command_topic"],
        64,
        hostname="localhost",
    )
    assert (
        messages_received["target_humidity_command_topic"].get(block=True, timeout=2)
        == "64"
    )


def test_set_current_temperature(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if (
        ClimateSetting.Capability.CURRENT_TEMPERATURE
        not in climate._settings.capability
    ):
        pytest.skip()
    climate.set_current_temperature(20)


def test_set_target_temperature(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.TARGET_TEMPERATURE not in climate._settings.capability:
        pytest.skip()
    climate.set_target_temperature(21)


def test_command_temperature(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.TARGET_TEMPERATURE not in climate._settings.capability:
        pytest.skip()

    publish.single(
        climate._command_topics["temperature_command_topic"],
        23,
        hostname="localhost",
    )
    assert (
        messages_received["temperature_command_topic"].get(block=True, timeout=2)
        == "23"
    )


def test_set_target_high_temperature(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if (
        ClimateSetting.Capability.TARGET_HIGH_TEMPERATURE
        not in climate._settings.capability
    ):
        pytest.skip()
    climate.set_target_high_temperature(22)


def test_command_high_temperature(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if (
        ClimateSetting.Capability.TARGET_HIGH_TEMPERATURE
        not in climate._settings.capability
    ):
        pytest.skip()

    publish.single(
        climate._command_topics["temperature_high_command_topic"],
        24,
        hostname="localhost",
    )
    assert (
        messages_received["temperature_high_command_topic"].get(block=True, timeout=2)
        == "24"
    )


def test_set_target_low_temperature(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if (
        ClimateSetting.Capability.TARGET_LOW_TEMPERATURE
        not in climate._settings.capability
    ):
        pytest.skip()
    climate.set_target_low_temperature(18)


def test_command_low_temperature(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if (
        ClimateSetting.Capability.TARGET_HIGH_TEMPERATURE
        not in climate._settings.capability
    ):
        pytest.skip()

    publish.single(
        climate._command_topics["temperature_low_command_topic"],
        18,
        hostname="localhost",
    )
    assert (
        messages_received["temperature_low_command_topic"].get(block=True, timeout=2)
        == "18"
    )


def test_set_fan_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.FAN_MODE not in climate._settings.capability:
        pytest.skip()

    assert climate._entity.fan_modes is not None
    assert len(climate._entity.fan_modes) > 0
    # sourcery skip: no-loop-in-tests
    for mode in climate._entity.fan_modes:
        climate.set_fan_mode(mode)


def test_command_fan_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.FAN_MODE not in climate._settings.capability:
        pytest.skip()

    publish.single(
        climate._command_topics["fan_mode_command_topic"],
        climate._entity.fan_modes[0],
        hostname="localhost",
    )
    assert (
        messages_received["fan_mode_command_topic"].get(block=True, timeout=2)
        == climate._entity.fan_modes[0]
    )


def test_set_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.MODE not in climate._settings.capability:
        pytest.skip()

    assert climate._entity.modes is not None
    assert len(climate._entity.modes) > 0
    # sourcery skip: no-loop-in-tests
    for mode in climate._entity.modes:
        climate.set_mode(mode)


def test_command_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.MODE not in climate._settings.capability:
        pytest.skip()

    publish.single(
        climate._command_topics["mode_command_topic"],
        climate._entity.modes[0],
        hostname="localhost",
    )
    assert (
        messages_received["mode_command_topic"].get(block=True, timeout=2)
        == climate._entity.modes[0]
    )


def test_power_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.POWER not in climate._settings.capability:
        pytest.skip()

    publish.single(
        climate._command_topics["power_command_topic"],
        climate._entity.payload_off,
        hostname="localhost",
    )
    assert (
        messages_received["power_command_topic"].get(block=True, timeout=2)
        == climate._entity.payload_off
    )


def test_set_preset_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.PRESET_MODE not in climate._settings.capability:
        pytest.skip()

    assert climate._entity.preset_modes is not None
    assert len(climate._entity.preset_modes) > 0
    # sourcery skip: no-loop-in-tests
    for mode in climate._entity.preset_modes:
        climate.set_preset_mode(mode)


def test_command_preset_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.PRESET_MODE not in climate._settings.capability:
        pytest.skip()

    publish.single(
        climate._command_topics["preset_mode_command_topic"],
        climate._entity.preset_modes[0],
        hostname="localhost",
    )
    assert (
        messages_received["preset_mode_command_topic"].get(block=True, timeout=2)
        == climate._entity.preset_modes[0]
    )


def test_set_swing_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.SWING_MODE not in climate._settings.capability:
        pytest.skip()

    assert climate._entity.swing_modes is not None
    assert len(climate._entity.swing_modes) > 0
    # sourcery skip: no-loop-in-tests
    for mode in climate._entity.swing_modes:
        climate.set_swing_mode(mode)


def test_command_swing_mode(climate: Climate):
    # sourcery skip: no-conditionals-in-tests
    if ClimateSetting.Capability.SWING_MODE not in climate._settings.capability:
        pytest.skip()

    publish.single(
        climate._command_topics["swing_mode_command_topic"],
        climate._entity.swing_modes[0],
        hostname="localhost",
    )
    assert (
        messages_received["swing_mode_command_topic"].get(block=True, timeout=2)
        == climate._entity.swing_modes[0]
    )
