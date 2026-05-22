import unittest

from pylabrobot.heating_shaking.opentrons_backend_usb import OpentronsHeaterShakerUSBBackend


class _FakeSerial:
  def __init__(self):
    self.writes = []
    self.responses = []
    self.stopped = False

  async def write(self, data: bytes):
    self.writes.append(data)

  async def readline(self):
    if len(self.responses) == 0:
      return b"OK\n"
    return self.responses.pop(0)

  async def stop(self):
    self.stopped = True


class OpentronsHeaterShakerUSBBackendTests(unittest.IsolatedAsyncioTestCase):
  def make_backend(self):
    backend = OpentronsHeaterShakerUSBBackend(port="/dev/ttyUSB0")
    serial = _FakeSerial()
    backend._serial = serial
    return backend, serial

  async def test_commands(self):
    backend, serial = self.make_backend()

    await backend.start_shaking(500)
    await backend.stop_shaking()
    await backend.lock_plate()
    await backend.unlock_plate()
    await backend.set_temperature(55)
    await backend.deactivate()

    self.assertEqual(
      serial.writes,
      [
        b"M3 S500\n",
        b"G28\n",
        b"M243\n",
        b"M242\n",
        b"M104 S55\n",
        b"M106\n",
      ],
    )

  async def test_live_data_parsing(self):
    backend, serial = self.make_backend()

    serial.responses = [b"T:55.00 C:25.50\n", b"OK\n"]
    self.assertEqual(await backend.get_current_temperature(), 25.5)
    serial.responses = [b"T:55.00 C:25.50\n", b"OK\n"]
    self.assertEqual(await backend.get_target_temperature(), 55.0)
    serial.responses = [b"T:500 C:488\n", b"OK\n"]
    self.assertEqual(await backend.get_current_speed(), 488)
    serial.responses = [b"T:0 C:0\n", b"OK\n"]
    self.assertIsNone(await backend.get_target_speed())
    serial.responses = [b"STATUS:IDLE_CLOSED\n", b"OK\n"]
    self.assertEqual(await backend.get_labware_latch_status(), "IDLE_CLOSED")
    serial.responses = [b"HW:A FW:21.2.1 SerialNo:HS123\n", b"OK\n"]
    self.assertEqual(
      await backend.get_device_info(),
      {"model": "A", "version": "21.2.1", "serial": "HS123"},
    )

  async def test_rejects_out_of_range_values(self):
    backend, _ = self.make_backend()

    with self.assertRaises(ValueError):
      await backend.start_shaking(199)
    with self.assertRaises(ValueError):
      await backend.set_temperature(36)
