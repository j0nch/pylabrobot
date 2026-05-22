import re
from typing import Dict, Optional

from pylabrobot.heating_shaking.backend import HeaterShakerBackend
from pylabrobot.io.serial import Serial


class OpentronsHeaterShakerUSBBackend(HeaterShakerBackend):
  """Direct USB backend for the Opentrons Heater-Shaker GEN1."""

  MIN_TEMPERATURE_C = 37.0
  MAX_TEMPERATURE_C = 95.0
  MIN_SPEED_RPM = 200
  MAX_SPEED_RPM = 3000

  def __init__(self, port: str, timeout: float = 40.0):
    """Create a new direct USB backend.

    Args:
      port: Serial port for USB communication.
      timeout: Serial read timeout in seconds.
    """

    self.port = port
    self.timeout = timeout
    self._serial: Optional[Serial] = None

  @property
  def serial(self) -> Serial:
    if self._serial is None:
      raise RuntimeError("Serial device not initialized. Call setup() first.")
    return self._serial

  async def setup(self):
    self._serial = Serial(
      human_readable_device_name="Opentrons Heater-Shaker Module",
      port=self.port,
      baudrate=115200,
      write_timeout=10,
      timeout=self.timeout,
    )
    await self._serial.setup()

  async def stop(self):
    await self.stop_shaking()
    await self.deactivate()
    if self._serial is not None:
      await self._serial.stop()
      self._serial = None

  def serialize(self) -> dict:
    return {**super().serialize(), "port": self.port, "timeout": self.timeout}

  @property
  def supports_locking(self) -> bool:
    return True

  @property
  def supports_active_cooling(self) -> bool:
    return False

  @classmethod
  def _format_float(cls, value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")

  @classmethod
  def _parse_key_values(cls, response: str) -> Dict[str, str]:
    return {
      match.group("key"): match.group("value")
      for match in re.finditer(r"(?P<key>\S+):(?P<value>\S+)", response)
    }

  @classmethod
  def _parse_optional_float(cls, value: str) -> Optional[float]:
    return None if value.lower() == "none" else float(value)

  async def _send_command(self, command: str) -> str:
    await self.serial.write(f"{command}\n".encode("ascii"))

    response_lines = []
    while True:
      line = await self.serial.readline()
      if line == b"":
        raise TimeoutError(f"Timed out waiting for response to {command!r}")

      decoded = line.decode("ascii", errors="replace").strip()
      if decoded == "":
        continue

      lowered = decoded.lower()
      if lowered.startswith("err") or lowered.startswith("async"):
        raise RuntimeError(f"Opentrons Heater-Shaker returned error for {command!r}: {decoded}")

      if decoded.upper() == "OK":
        return "\n".join(response_lines)

      response_lines.append(decoded)

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
    await self._send_command(f"M3 S{speed}")

  async def stop_shaking(self):
    # Homing also stops shaking and returns the orbit to the fixed home position.
    await self._send_command("G28")

  async def lock_plate(self):
    await self._send_command("M243")

  async def unlock_plate(self):
    await self._send_command("M242")

  async def set_temperature(self, temperature: float):
    self._validate_temperature(temperature)
    await self._send_command(f"M104 S{self._format_float(temperature)}")

  async def get_current_temperature(self) -> float:
    response = await self._send_command("M105")
    data = self._parse_key_values(response)
    try:
      return round(float(data["C"]), 2)
    except KeyError:
      raise RuntimeError(f"Unexpected temperature response from Heater-Shaker: {response!r}")

  async def get_target_temperature(self) -> Optional[float]:
    response = await self._send_command("M105")
    data = self._parse_key_values(response)
    try:
      target = self._parse_optional_float(data["T"])
      return None if target is None else round(target, 2)
    except KeyError:
      raise RuntimeError(f"Unexpected temperature response from Heater-Shaker: {response!r}")

  async def deactivate(self):
    await self._send_command("M106")

  async def get_current_speed(self) -> int:
    response = await self._send_command("M123")
    data = self._parse_key_values(response)
    try:
      return int(round(float(data["C"])))
    except KeyError:
      raise RuntimeError(f"Unexpected RPM response from Heater-Shaker: {response!r}")

  async def get_target_speed(self) -> Optional[int]:
    response = await self._send_command("M123")
    data = self._parse_key_values(response)
    try:
      target = int(round(float(data["T"])))
      return None if target == 0 else target
    except KeyError:
      raise RuntimeError(f"Unexpected RPM response from Heater-Shaker: {response!r}")

  async def get_labware_latch_status(self) -> str:
    response = await self._send_command("M241")
    data = self._parse_key_values(response)
    try:
      return data["STATUS"]
    except KeyError:
      raise RuntimeError(f"Unexpected latch status response from Heater-Shaker: {response!r}")

  async def get_device_info(self) -> Dict[str, str]:
    response = await self._send_command("M115")
    data = self._parse_key_values(response)
    return {
      "model": data.get("HW", ""),
      "version": data.get("FW", ""),
      "serial": data.get("SerialNo", ""),
    }
