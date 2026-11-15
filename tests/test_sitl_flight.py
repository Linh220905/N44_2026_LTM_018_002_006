"""Safety and trajectory checks; never arms a vehicle during testing."""
import importlib.util
import pathlib
import unittest
from unittest import mock

PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sitl_flight.py"
spec = importlib.util.spec_from_file_location("sitl_flight", PATH)
flight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flight)


class SitlFlightTest(unittest.TestCase):
    def test_waypoints_stay_within_small_sitl_area(self) -> None:
        for x, y, z in flight.WAYPOINTS:
            self.assertLessEqual(abs(x), 3)
            self.assertLessEqual(abs(y), 3)
            self.assertTrue(-3 <= z <= -1)

    def test_refuse_hardware_and_unknown_px4_process(self) -> None:
        self.assertTrue(flight.is_local_sitl(str(flight.PX4_EXECUTABLE)))
        self.assertFalse(flight.is_local_sitl("/usr/local/bin/px4"))
        self.assertFalse(flight.is_local_sitl(str(pathlib.Path.home() / "PX4-Autopilot/build/px4_fmu-v6x_default/bin/px4")))

    def test_preview_does_not_arm(self) -> None:
        with mock.patch.object(flight.mavutil, "mavlink_connection", side_effect=AssertionError("connected")):
            flight.main([])

    def test_refuses_already_armed_vehicle_before_setpoints(self) -> None:
        heartbeat = mock.Mock(
            autopilot=flight.mavutil.mavlink.MAV_AUTOPILOT_PX4,
            type=flight.mavutil.mavlink.MAV_TYPE_QUADROTOR,
            base_mode=flight.mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED,
        )
        link = mock.Mock(target_system=1, target_component=1)
        link.wait_heartbeat.return_value = heartbeat
        with mock.patch.object(flight, "is_sitl_running", return_value=True), \
             mock.patch.object(flight.mavutil, "mavlink_connection", return_value=link):
            with self.assertRaisesRegex(RuntimeError, "already armed"):
                flight.run_demo()
        link.mav.set_position_target_local_ned_send.assert_not_called()
        link.mav.command_long_send.assert_not_called()
        link.close.assert_called_once()

    def test_requests_land_if_arm_sent_but_confirmation_missing(self) -> None:
        idle = mock.Mock(
            autopilot=flight.mavutil.mavlink.MAV_AUTOPILOT_PX4,
            type=flight.mavutil.mavlink.MAV_TYPE_QUADROTOR,
            base_mode=0,
        )
        link = mock.Mock(target_system=1, target_component=1)
        link.wait_heartbeat.return_value = idle
        link.recv_match.return_value = None
        with mock.patch.object(flight, "is_sitl_running", return_value=True), \
             mock.patch.object(flight.mavutil, "mavlink_connection", return_value=link), \
             mock.patch.object(flight.time, "sleep", return_value=None), \
             mock.patch.object(flight.time, "monotonic", side_effect=[0, 0, 3, 3, 9, 9, 10]):
            with self.assertRaisesRegex(RuntimeError, "did not ARM"):
                flight.run_demo()
        commands = [call.args[2] for call in link.mav.command_long_send.call_args_list]
        self.assertIn(flight.mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, commands)
        self.assertIn(flight.mavutil.mavlink.MAV_CMD_NAV_LAND, commands)
        link.close.assert_called_once()

    def test_flight_refuses_when_sitl_not_running(self) -> None:
        with mock.patch.object(flight, "is_sitl_running", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "PX4 SITL"):
                flight.main(["--execute-sitl"])


if __name__ == "__main__":
    unittest.main()
