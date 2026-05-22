import asyncio
import time
from typing import Any, Dict, Optional, cast

from pylabrobot.heating_shaking.backend import HeaterShakerBackend

try:
  import ot_api

  USE_OT = True
except ImportError as e:
  USE_OT = False
  _OT_IMPORT_ERROR = e


class OpentronsHeaterShakerBackend(HeaterShakerBackend):
  """Backend that drives an Opentrons Heater-Shaker via the Opentrons HTTP API."""

  MIN_TEMPERATURE_C = 37.0
  MAX_TEMPERATURE_C = 95.0
  MIN_SPEED_RPM = 200
  MAX_SPEED_RPM = 3000

  def __init__(self, opentrons_id: str, command_timeout: float = 120.0):
    """Create a new Opentrons Heater-Shaker backend.

    Args:
      opentrons_id: Opentrons ID of the Heater-Shaker module. Get it from
        `OpentronsBackend(host="x.x.x.x", port=31950).list_connected_modules()`.
      command_timeout: Seconds to wait for robot-server commands to finish.
    """

    if not USE_OT:
      raise RuntimeError(
        "Opentrons is not installed. Please run pip install pylabrobot[opentrons]."
        f" Import error: {_OT_IMPORT_ERROR}."
      )

    self.opentrons_id = opentrons_id
    self.command_timeout = command_timeout

  async def setup(self):
    pass

  async def stop(self):
    await self.stop_shaking()
    await self.deactivate()

  def serialize(self) -> dict:
    return {
      **super().serialize(),
      "opentrons_id": self.opentrons_id,
      "command_timeout": self.command_timeout,
    }

  @property
  def supports_locking(self) -> bool:
    return True

  @property
  def supports_active_cooling(self) -> bool:
    return False

  async def _execute_command(
    self,
    command_type: str,
    params: Dict[str, Any],
    *,
    timeout: Optional[float] = None,
  ) -> dict:
    command_id = ot_api.runs.enqueue_command(
      command_type,
      params,
      intent="setup",
    )

    timeout_seconds = timeout if timeout is not None else self.command_timeout
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
      result = ot_api.runs.get_command(command_id)
      status = result["data"]["status"]

      if status == "failed":
        error = result["data"].get("error", {})
        error_type = error.get("errorType", "unknown")
        detail = error.get("detail", result)
        raise RuntimeError(f"Opentrons command {command_type!r} failed with {error_type}: {detail}")

      if status not in {"queued", "running"}:
        return cast(dict, result)

      await asyncio.sleep(0.1)

    raise TimeoutError(
      f"Opentrons command {command_type!r} did not finish within {timeout_seconds} seconds"
    )

  def _find_module(self) -> dict:
    for module in ot_api.modules.list_connected_modules():
      if module["id"] == self.opentrons_id:
        return cast(dict, module)
    raise RuntimeError(f"Opentrons Heater-Shaker module with id {self.opentrons_id!r} not found")

  def _get_module_data(self) -> dict:
    data = self._find_module().get("data")
    if not isinstance(data, dict):
      raise RuntimeError(f"Opentrons module {self.opentrons_id!r} has no data payload")
    return data

  def _get_float_from_module_data(self, *keys: str) -> float:
    data = self._get_module_data()
    for key in keys:
      value = data.get(key)
      if value is not None:
        return float(value)
    raise RuntimeError(
      f"Opentrons module {self.opentrons_id!r} data has none of the expected keys: {keys}"
    )

  @classmethod
  def _validate_temperature(cls, temperature: float) -> None:
    if not cls.MIN_TEMPERATURE_C <= temperature <= cls.MAX_TEMPERATURE_C:
      raise ValueError(
        f"Temperature {temperature} C is out of range. "
        f"Allowed range is {cls.MIN_TEMPERATURE_C:g}-{cls.MAX_TEMPERATURE_C:g} C."
      )

  @classmethod
  def _validate_speed(cls, speed: float) -> int:
    if isinstance(speed, float):
      if not speed.is_integer():
        raise ValueError(f"Speed must be a whole number of RPM, not {speed}")
      speed = int(speed)
    if not isinstance(speed, int):
      raise TypeError(f"Speed must be an integer or whole number float, not {type(speed).__name__}")
    if not cls.MIN_SPEED_RPM <= speed <= cls.MAX_SPEED_RPM:
      raise ValueError(
        f"Speed {speed} RPM is out of range. "
        f"Allowed range is {cls.MIN_SPEED_RPM}-{cls.MAX_SPEED_RPM} RPM."
      )
    return speed

  async def start_shaking(self, speed: float):
    speed = self._validate_speed(speed)
    await self._execute_command(
      "heaterShaker/setAndWaitForShakeSpeed",
      {"moduleId": self.opentrons_id, "rpm": speed},
    )

  async def stop_shaking(self):
    await self._execute_command(
      "heaterShaker/deactivateShaker",
      {"moduleId": self.opentrons_id},
    )

  async def lock_plate(self):
    await self._execute_command(
      "heaterShaker/closeLabwareLatch",
      {"moduleId": self.opentrons_id},
    )

  async def unlock_plate(self):
    await self._execute_command(
      "heaterShaker/openLabwareLatch",
      {"moduleId": self.opentrons_id},
    )

  async def set_temperature(self, temperature: float):
    self._validate_temperature(temperature)
    await self._execute_command(
      "heaterShaker/setTargetTemperature",
      {"moduleId": self.opentrons_id, "celsius": temperature},
    )

  async def deactivate(self):
    await self._execute_command(
      "heaterShaker/deactivateHeater",
      {"moduleId": self.opentrons_id},
    )

  async def get_current_temperature(self) -> float:
    return self._get_float_from_module_data("currentTemperature", "currentTemp")

  async def get_target_temperature(self) -> Optional[float]:
    data = self._get_module_data()
    target = data.get("targetTemperature", data.get("targetTemp"))
    return None if target is None else float(target)

  async def get_current_speed(self) -> int:
    return int(self._get_float_from_module_data("currentSpeed"))

  async def get_target_speed(self) -> Optional[int]:
    data = self._get_module_data()
    target = data.get("targetSpeed")
    return None if target is None else int(target)

  async def get_labware_latch_status(self) -> str:
    data = self._get_module_data()
    status = data.get("labwareLatchStatus")
    if not isinstance(status, str):
      raise RuntimeError(f"Opentrons module {self.opentrons_id!r} has no latch status")
    return status
