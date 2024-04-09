import logging

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant

from custom_components.dual_smart_thermostat.hvac_device.controllable_hvac_device import (
    ControlableHVACDevice,
)
from custom_components.dual_smart_thermostat.hvac_device.cooler_device import (
    CoolerDevice,
)
from custom_components.dual_smart_thermostat.hvac_device.fan_device import FanDevice
from custom_components.dual_smart_thermostat.hvac_device.hvac_device import (
    HVACDevice,
    merge_hvac_modes,
)
from custom_components.dual_smart_thermostat.managers.opening_manager import (
    OpeningManager,
)
from custom_components.dual_smart_thermostat.managers.temperature_manager import (
    TemperatureManager,
)

_LOGGER = logging.getLogger(__name__)


class CoolerFanDevice(HVACDevice, ControlableHVACDevice):

    def __init__(
        self,
        hass: HomeAssistant,
        cooler_device: CoolerDevice,
        fan_device: FanDevice,
        initial_hvac_mode: HVACMode,
        temperatures: TemperatureManager,
        openings: OpeningManager,
        range_mode: bool = False,
    ) -> None:
        super().__init__(hass, temperatures, openings)

        self._device_type = self.__class__.__name__
        self.cooler_device = cooler_device
        self.fan_device = fan_device

        if range_mode:
            self._target_temp_attr = "_target_temp_high"

        # _hvac_modes are the combined values of the cooler_device.hvac_modes and fan_device.hvac_modes without duplicates
        self.hvac_modes = merge_hvac_modes(
            cooler_device.hvac_modes, fan_device.hvac_modes
        )

        if initial_hvac_mode in self.hvac_modes:
            self._hvac_mode = initial_hvac_mode
        else:
            self._hvac_mode = None

    def set_context(self, context: Context):
        self.cooler_device.set_context(context)
        self.fan_device.set_context(context)
        self._context = context

    def get_device_ids(self) -> list[str]:
        return [self.cooler_device.entity_id, self.fan_device.entity_id]

    def is_active(self) -> bool:
        return self.cooler_device.is_active() or self.fan_device.is_active()

    @property
    def hvac_action(self) -> HVACAction:
        if self.cooler_device.is_active:
            return HVACAction.COOLING
        if self.fan_device.is_active:
            return HVACAction.FAN
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode

    @hvac_mode.setter
    def hvac_mode(self, hvac_mode: HVACMode):
        self._hvac_mode = hvac_mode

    def on_startup(self):

        entity_state1 = self.hass.states.get(self.cooler_device.entity_id)
        entity_state2 = self.hass.states.get(self.fan_device.entity_id)
        if entity_state1 and entity_state1.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            self.hass.loop.create_task(self._async_check_device_initial_state())

        if entity_state2 and entity_state2.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            self.hass.loop.create_task(self._async_check_device_initial_state())

    async def _async_check_device_initial_state(self) -> None:
        """Prevent the device from keep running if HVACMode.OFF."""
        if self._hvac_mode == HVACMode.OFF and self.is_active:
            _LOGGER.warning(
                "The climate mode is OFF, but the switch device is ON. Turning off device %s, %s",
                self.cooler_device.entity_id,
                self.fan_device.entity_id,
            )
            await self.async_turn_off()

    async def async_control_hvac(self, time=None, force=False):
        _LOGGER.info({self.__class__.__name__})
        match self._hvac_mode:
            case HVACMode.COOL:
                await self.cooler_device.async_control_hvac(time, force)
            case HVACMode.FAN_ONLY:
                await self.fan_device.async_control_hvac(time, force)
            case HVACMode.OFF:
                await self.async_turn_off()
            case _:
                _LOGGER.warning("Invalid HVAC mode: %s", self._hvac_mode)

    async def async_turn_on(self):
        """self._control_hvac will handle the logic for turning on the heater and aux heater."""
        pass

    async def async_turn_off(self):
        await self.cooler_device.async_turn_off()
        await self.fan_device.async_turn_off()
