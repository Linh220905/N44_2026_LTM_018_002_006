#!/usr/bin/env python3
"""Optional short Offboard demo for localhost PX4 SITL only; preview by default.

Never use against real hardware. QGroundControl and jMAVSim remain separate UIs.
"""
import argparse
import os
import time
from pathlib import Path

from pymavlink import mavutil

# Local NED: x=north, y=east, z=down; all targets near home.
WAYPOINTS = ((0.0, 0.0, -2.0), (2.0, 0.0, -2.0),
             (2.0, 2.0, -2.0), (0.0, 0.0, -2.0))
PX4_EXECUTABLE = Path.home() / "PX4-Autopilot/build/px4_sitl_default/bin/px4"
PX4_UDP_PORT = 14580
SETPOINT_MASK = 0b110111111000  # Position x/y/z only; ignore velocity, acceleration, yaw.


def is_local_sitl(executable: str) -> bool:
    return Path(executable) == PX4_EXECUTABLE


def is_sitl_running() -> bool:
    try:
        for process in Path("/proc").iterdir():
            if not process.name.isdecimal():
                continue
            try:
                if is_local_sitl(os.readlink(process / "exe")):
                    return True
            except (OSError, PermissionError):
                continue
    except OSError:
        return False
    return False


def position_setpoint(link: mavutil.mavfile, target: tuple[float, float, float]) -> None:
    link.mav.set_position_target_local_ned_send(
        0, link.target_system, link.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED, SETPOINT_MASK,
        *target, 0, 0, 0, 0, 0, 0, 0, 0)


def command(link: mavutil.mavfile, number: int, *values: float) -> None:
    link.mav.command_long_send(link.target_system, link.target_component,
                               number, 0, *(list(values) + [0.0] * (7 - len(values))))


def run_demo() -> None:
    if not is_sitl_running():
        raise RuntimeError("PX4 SITL process not running at expected executable; refusing to arm")
    link = mavutil.mavlink_connection(f"udpout:127.0.0.1:{PX4_UDP_PORT}", source_system=245)
    started = time.monotonic()
    arm_sent = False
    armed = False
    try:
        # PX4 does not send telemetry to new udpout peers until they transmit.
        link.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                                0, 0, mavutil.mavlink.MAV_STATE_ACTIVE)
        heartbeat = link.wait_heartbeat(timeout=8)
        if heartbeat is None or heartbeat.autopilot != mavutil.mavlink.MAV_AUTOPILOT_PX4 or \
           heartbeat.type != mavutil.mavlink.MAV_TYPE_QUADROTOR or not is_sitl_running():
            raise RuntimeError("PX4 SITL heartbeat not verified; no ARM command sent")
        if heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
            raise RuntimeError("PX4 is already armed; refusing to take control")
        print("PX4 SITL verified. Offboard setpoints 10 Hz; QGroundControl shows live position.", flush=True)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            position_setpoint(link, WAYPOINTS[0])
            time.sleep(0.1)
        link.set_mode("OFFBOARD")
        command(link, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        arm_sent = True
        confirmation = time.monotonic() + 5
        while time.monotonic() < confirmation:
            position_setpoint(link, WAYPOINTS[0])
            message = link.recv_match(type="HEARTBEAT", blocking=True, timeout=0.1)
            if message and message.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
                armed = True
                break
        if not armed:
            raise RuntimeError("PX4 did not ARM; inspect QGroundControl vehicle messages")
        print("ARMED on SITL. Watching QGroundControl and jMAVSim.", flush=True)
        for index, target in enumerate(WAYPOINTS, 1):
            print(f"Waypoint {index}/{len(WAYPOINTS)}: NED {target}", flush=True)
            end = time.monotonic() + 5
            while time.monotonic() < end:
                if not is_sitl_running():
                    raise RuntimeError("PX4 SITL exited")
                position_setpoint(link, target)
                time.sleep(0.1)
    finally:
        if arm_sent:
            try:
                print("LAND requested. Keep QGroundControl open until disarmed.", flush=True)
                command(link, mavutil.mavlink.MAV_CMD_NAV_LAND)
            finally:
                link.close()
        else:
            link.close()
    print(f"SITL demo finished in {time.monotonic() - started:.1f}s; check landing in QGC.", flush=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Short PX4 SITL-only flight for QGC/jMAVSim")
    parser.add_argument("--execute-sitl", action="store_true", help="ARM the verified local PX4 SITL")
    arguments = parser.parse_args(argv)
    if not arguments.execute_sitl:
        print("PREVIEW: no MAVLink sent. With --execute-sitl: arm SITL, fly at 2m ",
              "through 4 waypoints (<=2m from home), then land.")
        return
    run_demo()


if __name__ == "__main__":
    main()
