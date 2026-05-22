import unittest

from pylabrobot.heating_shaking import (
  HeaterShaker,
  HeaterShakerChatterboxBackend,
  OpentronsHeaterShakerModuleV1,
)
from pylabrobot.resources.coordinate import Coordinate


class HeaterShakerTests(unittest.TestCase):
  def test_serialization(self):
    hs = HeaterShaker(
      name="test_hs",
      size_x=10,
      size_y=10,
      size_z=10,
      backend=HeaterShakerChatterboxBackend(),
      child_location=Coordinate(0, 0, 0),
    )

    serialized = hs.serialize()
    deserialized = HeaterShaker.deserialize(serialized)
    self.assertEqual(hs, deserialized)

  def test_opentrons_heater_shaker_serialization(self):
    hs = OpentronsHeaterShakerModuleV1(
      name="opentrons_hs",
      serial_port="/dev/ttyUSB0",
    )

    serialized = hs.serialize()
    deserialized = HeaterShaker.deserialize(serialized)
    self.assertEqual(hs, deserialized)
