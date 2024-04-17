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
from enum import Flag, Enum, auto
from typing import Any, Callable, Optional, TypeVar
from ha_mqtt_discoverable import (
    Discoverable,
    EntityInfo,
    EntityType,
    Settings,
)
import paho.mqtt.client as mqtt


class ClimateInfo(EntityInfo):
    """Climate specific information"""

    component: str = "climate"

    fan_modes: Optional[list[str]]
    """A list of supported fan modes. ["auto", "low", "medium", "high"]"""
    initial: Optional[float]
    """Set the initial target temperature. The default value depends on the temperature unit and will be 21° or 69.8°F"""
    max_humidity: Optional[float]
    """(default: 99) The minimum target humidity percentage that can be set."""
    max_temp: Optional[float]
    """Maximum set point available. The default value depends on the temperature unit, and will be 35°C or 95°F."""
    min_humidity: Optional[float]
    """(default: 30) The maximum target humidity percentage that can be set."""
    min_temp: Optional[float]
    """Minimum set point available. The default value depends on the temperature unit, and will be 7°C or 44.6°F."""
    modes: Optional[list[str]]
    """A list of supported modes. Needs to be a subset of the default values. ["auto", "off", "cool", "heat", "dry", "fan_only"]"""
    optimistic: Optional[bool]
    """Flag that defines if the climate works in optimistic mode
    Default: true if no state topic defined, else false."""
    payload_available: str = "online"
    """The payload that represents the available state."""
    payload_not_available: str = "offline"
    """The payload that represents the unavailable state"""
    payload_off: str = "off"
    """Payload to send for the ON state"""
    payload_on: str = "on"
    """Payload to send for the OFF state"""
    precision: Optional[float]
    """The desired precision for this device. Can be used to match your actual thermostat’s precision.
    Supported values are 0.1, 0.5 and 1.0.
    Default: 0.1 for Celsius and 1.0 for Fahrenheit."""
    preset_modes: Optional[list[str]]
    """List of preset modes this climate is supporting.
    Common examples include eco, away, boost, comfort, home, sleep and activity."""
    swing_modes: Optional[list[str]]
    """A list of supported swing modes. ["on", "off"] """
    temperature_unit: Optional[str]
    """Defines the temperature unit of the device, C or F.
    If this is not set, the temperature unit is set to the system temperature unit."""
    temp_step: float = 1
    """Step size for temperature set point."""


class ClimateSetting(Settings[EntityType]):
    class Capability(Flag):
        ACTION = auto()
        CURRENT_HUMIDITY = auto()
        CURRENT_TEMPERATURE = auto()
        FAN_MODE = auto()
        MODE = auto()
        POWER = auto()
        PRESET_MODE = auto()
        SWING_MODE = auto()
        TARGET_HUMIDITY = auto()
        TARGET_TEMPERATURE = auto()
        TARGET_HIGH_TEMPERATURE = auto()
        TARGET_LOW_TEMPERATURE = auto()

    capability: Optional[Capability]
    """Capability of the device as Flag"""


# This Python class named Climate is a Discoverable class for BinarySensorInfo and a Subscriber class
# for SwitchInfo.
class Climate(Discoverable[ClimateInfo]):
    _settings: ClimateSetting
    _state_topics: dict[str, str] = {}
    _command_topics: dict[str, str] = {}

    T = TypeVar("T")  # Used in the callback function

    def __init__(
        self,
        settings: ClimateSetting,
        command_callbacks: dict[str, Callable[[mqtt.Client, T, mqtt.MQTTMessage], Any]],
        user_data: T = None,
    ) -> None:
        """
        Entity that listens to commands from an MQTT topic.

        Args:
            settings: Settings for the entity we want to create in Home Assistant.
            See the `Settings` class for the available options.
            command_callbacks: A dict of Callback function invoked when there is a command
            coming from the MQTT command topic. The dict key is the topic name
        """

        # Callback invoked when the MQTT connection is established
        def on_client_connected(client: mqtt.Client, *args):
            # Publish this button in Home Assistant
            # Subscribe to the command topic
            result, _ = client.subscribe(
                f"{self._settings.mqtt.state_prefix}/{self._entity_topic}/command/#",
                qos=1,
            )
            if result is not mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError("Error subscribing to MQTT command topic")
            self.write_config()
            for key, value in self._command_topics.items():
                if key in command_callbacks:
                    self.mqtt_client.message_callback_add(
                        value,
                        command_callbacks[key],
                    )

        # Invoke the parent init
        super().__init__(settings, on_client_connected)
        self._settings = settings

        # Default values based on capability
        if self._settings.capability:
            if (
                ClimateSetting.Capability.FAN_MODE in self._settings.capability
                and not self._entity.fan_modes
            ):
                self._entity.fan_modes = ["auto", "low", "medium", "high"]
            if (
                ClimateSetting.Capability.MODE in self._settings.capability
                and not self._entity.modes
            ):
                self._entity.modes = ["auto", "off", "cool", "heat", "dry", "fan_only"]
            if (
                ClimateSetting.Capability.SWING_MODE in self._settings.capability
                and not self._entity.swing_modes
            ):
                self._entity.swing_modes = ["on", "off"]

        # Register the user-supplied callback function with its user_data
        self.mqtt_client.user_data_set(user_data)
        # Manually connect the MQTT client
        self._connect_client()

    def generate_config(self) -> dict[str, Any]:
        """
        Generate a dictionary that we'll grind into JSON and write to MQTT.

        Will be used with the MQTT discovery protocol to make Home Assistant
        automagically ingest the new sensor.
        """
        self.state_topic = "bogus"
        config = super().generate_config()
        # Remove Unusefull Property
        delattr(self, "state_topic")
        del config["state_topic"]

        def addStateTopic(key: str):
            config[key] = (
                f"{self._settings.mqtt.state_prefix}/{self._entity_topic}/state/"
                f"{key.removesuffix('_topic').removesuffix('_state')}"
            )
            self._state_topics[key] = config[key]

        def addCommandTopic(key: str):
            config[key] = (
                f"{self._settings.mqtt.state_prefix}/{self._entity_topic}/command/"
                f"{key.removesuffix('_topic').removesuffix('_command')}"
            )
            self._command_topics[key] = config[key]

        # Add specific climate topics
        if self._settings.capability:
            if ClimateSetting.Capability.ACTION in self._settings.capability:
                addStateTopic("action_topic")
            if ClimateSetting.Capability.CURRENT_HUMIDITY in self._settings.capability:
                addStateTopic("current_humidity_topic")
            if (
                ClimateSetting.Capability.CURRENT_TEMPERATURE
                in self._settings.capability
            ):
                addStateTopic("current_temperature_topic")
            if ClimateSetting.Capability.FAN_MODE in self._settings.capability:
                addStateTopic("fan_mode_state_topic")
                addCommandTopic("fan_mode_command_topic")
            if ClimateSetting.Capability.MODE in self._settings.capability:
                addStateTopic("mode_state_topic")
                addCommandTopic("mode_command_topic")
            if ClimateSetting.Capability.POWER in self._settings.capability:
                addCommandTopic("power_command_topic")
            if ClimateSetting.Capability.PRESET_MODE in self._settings.capability:
                addStateTopic("preset_mode_state_topic")
                addCommandTopic("preset_mode_command_topic")
            if ClimateSetting.Capability.SWING_MODE in self._settings.capability:
                addStateTopic("swing_mode_state_topic")
                addCommandTopic("swing_mode_command_topic")
            if ClimateSetting.Capability.TARGET_HUMIDITY in self._settings.capability:
                addStateTopic("target_humidity_state_topic")
                addCommandTopic("target_humidity_command_topic")
            if (
                ClimateSetting.Capability.TARGET_TEMPERATURE
                in self._settings.capability
            ):
                addStateTopic("temperature_state_topic")
                addCommandTopic("temperature_command_topic")
            if (
                ClimateSetting.Capability.TARGET_HIGH_TEMPERATURE
                in self._settings.capability
            ):
                addStateTopic("temperature_high_state_topic")
                addCommandTopic("temperature_high_command_topic")
            if (
                ClimateSetting.Capability.TARGET_LOW_TEMPERATURE
                in self._settings.capability
            ):
                addStateTopic("temperature_low_state_topic")
                addCommandTopic("temperature_low_command_topic")
        return config

    class Action(str, Enum):
        OFF = "off"
        HEATING = "heating"
        COOLING = "cooling"
        DRYING = "drying"
        IDLE = "idle"
        FAN = "fan"

    def _capability_state_helper(
        self, capability: ClimateSetting.Capability, state: str, topic: str
    ):
        if capability not in self._settings.capability:
            raise RuntimeError("Action is not configured for this entity!")
        result = self._state_helper(state, topic=topic)
        if result.rc is not mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"Error sending state {state} to MQTT {topic} topic {result.rc}"
            )

    def set_action(self, action: Action):
        state = action.value
        topic = self._state_topics["action_topic"]
        self._capability_state_helper(ClimateSetting.Capability.ACTION, state, topic)

    def set_current_humidity(self, humidity: float):
        topic = self._state_topics["current_humidity_topic"]
        state = str(humidity)
        self._capability_state_helper(
            ClimateSetting.Capability.CURRENT_HUMIDITY, state, topic
        )

    def set_target_humidity(self, humidity: float):
        topic = self._state_topics["target_humidity_state_topic"]
        state = str(humidity)
        self._capability_state_helper(
            ClimateSetting.Capability.TARGET_HUMIDITY, state, topic
        )

    def set_current_temperature(self, temperature: float):
        topic = self._state_topics["current_temperature_topic"]
        state = str(temperature)
        self._capability_state_helper(
            ClimateSetting.Capability.CURRENT_TEMPERATURE, state, topic
        )

    def set_target_temperature(self, temperature: float):
        topic = self._state_topics["temperature_state_topic"]
        state = str(temperature)
        self._capability_state_helper(
            ClimateSetting.Capability.TARGET_TEMPERATURE, state, topic
        )

    def set_target_high_temperature(self, temperature: float):
        topic = self._state_topics["temperature_high_state_topic"]
        state = str(temperature)
        self._capability_state_helper(
            ClimateSetting.Capability.TARGET_HIGH_TEMPERATURE, state, topic
        )

    def set_target_low_temperature(self, temperature: float):
        topic = self._state_topics["temperature_low_state_topic"]
        state = str(temperature)
        self._capability_state_helper(
            ClimateSetting.Capability.TARGET_LOW_TEMPERATURE, state, topic
        )

    def set_fan_mode(self, fan_mode: str):
        if fan_mode not in self._entity.fan_modes:
            raise RuntimeError(
                f"Error sending fan mode {fan_mode} not valid value accepted are {self._entity.fan_modes}"
            )
        topic = self._state_topics["fan_mode_state_topic"]
        state = fan_mode
        self._capability_state_helper(ClimateSetting.Capability.FAN_MODE, state, topic)

    def set_mode(self, mode: str):
        if mode not in self._entity.modes:
            raise RuntimeError(
                f"Error sending mode {mode} not valid value accepted are {self._entity.modes}"
            )
        topic = self._state_topics["mode_state_topic"]
        state = mode
        self._capability_state_helper(ClimateSetting.Capability.MODE, state, topic)

    def set_preset_mode(self, preset_mode: str):
        if preset_mode not in self._entity.preset_modes:
            raise RuntimeError(
                f"Error sending preset mode {preset_mode} not valid value accepted are {self._entity.preset_modes}"
            )
        topic = self._state_topics["preset_mode_state_topic"]
        state = preset_mode
        self._capability_state_helper(
            ClimateSetting.Capability.PRESET_MODE, state, topic
        )

    def set_swing_mode(self, swing_mode: str):
        if swing_mode not in self._entity.swing_modes:
            raise RuntimeError(
                f"Error sending preset mode {swing_mode} not valid value accepted are {self._entity.swing_modes}"
            )
        topic = self._state_topics["swing_mode_state_topic"]
        state = swing_mode
        self._capability_state_helper(
            ClimateSetting.Capability.SWING_MODE, state, topic
        )
