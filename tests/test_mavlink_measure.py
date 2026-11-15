"""Exercise measurement through real localhost UDP frames, without PX4."""
import pathlib
import socket
import subprocess
import time

from pymavlink import mavutil
from pymavlink.dialects.v20 import all as dialect

ROOT = pathlib.Path(__file__).resolve().parents[1]
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]

process = subprocess.Popen(
    [str(pathlib.Path(__import__("sys").executable)), "-I",
     str(ROOT / "scripts/measure_mavlink.py"), "--port", str(port),
     "--seconds", "1"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
)
try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        mav = mavutil.mavlink.MAVLink(None, srcSystem=1, srcComponent=1)
        time.sleep(0.3)
        for sequence in (254, 255, 1, 2):
            mav.seq = sequence
            message = mav.heartbeat_encode(mavutil.mavlink.MAV_TYPE_QUADROTOR,
                                           mavutil.mavlink.MAV_AUTOPILOT_PX4,
                                           0, 0, mavutil.mavlink.MAV_STATE_STANDBY)
            sender.sendto(message.pack(mav), ("127.0.0.1", port))
            time.sleep(0.05)
        # Unknown MAVLink v2 ID in active dialect: pymavlink assigns source/seq=0,
        # but wire header remains valid and must count toward sequence continuity.
        # Use MAVLink v2 unknown message with valid wire header/source.
        mav2 = dialect.MAVLink(None, srcSystem=1, srcComponent=1)
        mav2.seq = 3
        message2 = mav2.heartbeat_encode(mavutil.mavlink.MAV_TYPE_QUADROTOR,
                                         mavutil.mavlink.MAV_AUTOPILOT_PX4,
                                         0, 0, mavutil.mavlink.MAV_STATE_STANDBY)
        unknown = bytearray(message2.pack(mav2))
        unknown[7:10] = (291).to_bytes(3, "little")
        sender.sendto(unknown, ("127.0.0.1", port))
    output, error = process.communicate(timeout=5)
    assert process.returncode == 0, error
    assert "received=5" in output, output
    assert "missing_estimate=1" in output, output
    assert "loss_estimate=16.67%" in output, output
    print("MAVLink measurement test passed")
finally:
    if process.poll() is None:
        process.kill()
        process.communicate()
