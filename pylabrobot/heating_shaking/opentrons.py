from typing import Optional

from pylabrobot.heating_shaking.backend import HeaterShakerBackend
from pylabrobot.heating_shaking.heater_shaker import HeaterShaker
from pylabrobot.heating_shaking.opentrons_backend import OpentronsHeaterShakerBackend
from pylabrobot.heating_shaking.opentrons_backend_usb import OpentronsHeaterShakerUSBBackend
from pylabrobot.resources import Coordinate, ItemizedResource
from pylabrobot.resources.opentrons.module import OTModule


class OpentronsHeaterShakerModuleV1(HeaterShaker, OTModule):
  """Opentrons Heater-Shaker Module GEN1.

  Supports both Opentrons robot-server control (`opentrons_id`) and direct USB serial
  control (`serial_port`).
  """

  def __init__(
    self,
    name: str,
    opentrons_id: Optional[str] = None,
    serial_port: Optional[str] = None,
    child_location: Coordinate = Coordinate(0, 0, 82),
    child: Optional[ItemizedResource] = None,
    backend: Optional[HeaterShakerBackend] = None,
    size_x: float = 152.0,
    size_y: float = 90.0,
    size_z: float = 82.0,
    category: str = "heating_shaking",
    model: str = "heaterShakerModuleV1",
  ):
    """Create a new Opentrons Heater-Shaker Module GEN1.

    Args:
      name: Name of the Heater-Shaker module.
      opentrons_id: Opentrons ID of the module. Get it from
        `OpentronsBackend(host="x.x.x.x", port=31950).list_connected_modules()`.
        Exactly one of `opentrons_id` or `serial_port` must be provided.
      serial_port: Serial port for direct USB communication. Exactly one of
        `opentrons_id` or `serial_port` must be provided.
      child_location: Default child location for a mounted adapter, plate, or other resource.
      child: Optional child resource like a plate adapter or well plate.
    """

    backend_options = [backend is not None, opentrons_id is not None, serial_port is not None]
    if backend_options.count(True) != 1:
      raise ValueError(
        "Exactly one of `backend`, `opentrons_id`, or `serial_port` must be provided."
      )

    if backend is None:
      if serial_port is not None:
        backend = OpentronsHeaterShakerUSBBackend(port=serial_port)
      else:
        assert opentrons_id is not None
        backend = OpentronsHeaterShakerBackend(opentrons_id=opentrons_id)

    super().__init__(
      name=name,
      size_x=size_x,
      size_y=size_y,
      size_z=size_z,
      backend=backend,
      child_location=child_location,
      category=category,
      model=model,
    )

    self.child = child

    if child is not None:
      self.assign_child_resource(child)

  async def open_labware_latch(self):
    await self.unlock_plate()

  async def close_labware_latch(self):
    await self.lock_plate()

  async def deactivate_heater(self):
    await self.deactivate()

  async def deactivate_shaker(self):
    await self.stop_shaking()
