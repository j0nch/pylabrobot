import unittest

from pylabrobot.heating_shaking.opentrons_backend import OpentronsHeaterShakerBackend
import pylabrobot.heating_shaking.opentrons_backend as opentrons_backend_module


class _FakeRuns:
  def __init__(self):
    self.commands = []

  def enqueue_command(self, command, params, intent, run_id=None):
    self.commands.append((command, params, intent))
    return f"command-{len(self.commands)}"

  def get_command(self, command_id, run_id=None):
    return {"data": {"id": command_id, "status": "succeeded"}}


class _FakeModules:
  def list_connected_modules(self):
    return [
      {
        "id": "heater-shaker-id",
        "moduleModel": "heaterShakerModuleV1",
        "data": {
          "currentTemperature": 23.4,
          "targetTemperature": 55.0,
          "currentSpeed": 500,
          "targetSpeed": 500,
          "labwareLatchStatus": "closed",
        },
      }
    ]


class _FakeOTAPI:
  def __init__(self):
    self.runs = _FakeRuns()
    self.modules = _FakeModules()


class OpentronsHeaterShakerBackendTests(unittest.IsolatedAsyncioTestCase):
  def setUp(self):
    self._old_use_ot = opentrons_backend_module.USE_OT
    self._old_ot_api = getattr(opentrons_backend_module, "ot_api", None)
    self.fake_ot_api = _FakeOTAPI()
    opentrons_backend_module.USE_OT = True
    opentrons_backend_module.ot_api = self.fake_ot_api

  def tearDown(self):
    opentrons_backend_module.USE_OT = self._old_use_ot
    if self._old_ot_api is None:
      del opentrons_backend_module.ot_api
    else:
      opentrons_backend_module.ot_api = self._old_ot_api

  async def test_commands(self):
    backend = OpentronsHeaterShakerBackend("heater-shaker-id")

    await backend.start_shaking(500)
    await backend.stop_shaking()
    await backend.lock_plate()
    await backend.unlock_plate()
    await backend.set_temperature(55)
    await backend.deactivate()

    self.assertEqual(
      self.fake_ot_api.runs.commands,
      [
        (
          "heaterShaker/setAndWaitForShakeSpeed",
          {"moduleId": "heater-shaker-id", "rpm": 500},
          "setup",
        ),
        ("heaterShaker/deactivateShaker", {"moduleId": "heater-shaker-id"}, "setup"),
        ("heaterShaker/closeLabwareLatch", {"moduleId": "heater-shaker-id"}, "setup"),
        ("heaterShaker/openLabwareLatch", {"moduleId": "heater-shaker-id"}, "setup"),
        (
          "heaterShaker/setTargetTemperature",
          {"moduleId": "heater-shaker-id", "celsius": 55},
          "setup",
        ),
        ("heaterShaker/deactivateHeater", {"moduleId": "heater-shaker-id"}, "setup"),
      ],
    )

  async def test_live_data_accessors(self):
    backend = OpentronsHeaterShakerBackend("heater-shaker-id")

    self.assertEqual(await backend.get_current_temperature(), 23.4)
    self.assertEqual(await backend.get_target_temperature(), 55.0)
    self.assertEqual(await backend.get_current_speed(), 500)
    self.assertEqual(await backend.get_target_speed(), 500)
    self.assertEqual(await backend.get_labware_latch_status(), "closed")

  async def test_rejects_out_of_range_values(self):
    backend = OpentronsHeaterShakerBackend("heater-shaker-id")

    with self.assertRaises(ValueError):
      await backend.start_shaking(199)
    with self.assertRaises(ValueError):
      await backend.set_temperature(36)
