#!/usr/bin/env python3
"""Join the multicast group as a real receiver and dump the first DLSP frames from gcs_server.

Prints hex + decoded header of a HEARTBEAT, a SHOW_ARM_TRIGGER and a TIME_SYNC exchange,
saved to evidence/frames.json for the report (no root needed, unlike tcpdump).
"""
import json
import pathlib
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
GROUP = "239.255.0.1"
NAMES = {1: "HELLO_REQ", 2: "HELLO_ACK", 3: "TRAJECTORY_DATA", 4: "TIME_SYNC_REQ", 5: "TIME_SYNC_RESP",
         6: "SWARM_HEARTBEAT", 7: "SHOW_ARM_TRIGGER", 8: "EMERGENCY_STOP", 9: "SETPOINT"}


def crc16(frame: bytes) -> int:
    value = 0xFFFF
    for i, byte in enumerate(frame):
        value ^= (0 if i in (12, 13) else byte) << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021 if value & 0x8000 else value << 1) & 0xFFFF
    return value


def describe(frame: bytes) -> dict:
    magic, version, kind, seq, length, checksum, reserved = struct.unpack(">HBBIIHH", frame[:16])
    return {"hex": frame.hex(" "), "size": len(frame), "magic": f"0x{magic:04X}", "version": version,
            "type": f"0x{kind:02X} {NAMES.get(kind, '?')}", "seq": seq, "payload_len": length,
            "checksum": f"0x{checksum:04X}", "crc_ok": checksum == crc16(frame), "reserved": reserved}


def free_port(kind: int) -> int:
    with socket.socket(socket.AF_INET, kind) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def main() -> None:
    tcp, sync, mcast = free_port(socket.SOCK_STREAM), free_port(socket.SOCK_DGRAM), free_port(socket.SOCK_DGRAM)
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiver.bind(("", mcast))
    receiver.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                        socket.inet_aton(GROUP) + socket.inet_aton("127.0.0.1"))
    receiver.settimeout(5)
    with tempfile.TemporaryDirectory() as tmp:
        show = pathlib.Path(tmp, "show.bin")
        subprocess.run([sys.executable, "-I", str(ROOT / "scripts/generate_show.py"), "--drones", "1",
                        "--output", str(show)], check=True)
        gcs = subprocess.Popen([str(ROOT / "bin/gcs_server"), "--show", str(show), "--port", str(tcp),
                                "--sync-port", str(sync), "--multicast", f"{GROUP}:{mcast}"],
                               stdout=subprocess.DEVNULL)
        try:
            time.sleep(0.1)
            frames = {}
            heartbeat, _ = receiver.recvfrom(64)
            frames["heartbeat"] = describe(heartbeat)
            # one real time-sync exchange
            req = struct.pack(">HBBIIHH", 0x5058, 1, 4, 1, 8, 0, 0) + struct.pack(">Q", time.time_ns() // 1000)
            req = req[:12] + struct.pack(">H", crc16(req)) + req[14:]
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(2)
                client.sendto(req, ("127.0.0.1", sync))
                frames["time_sync_req"] = describe(req)
                frames["time_sync_resp"] = describe(client.recv(64))
            agent = subprocess.Popen([str(ROOT / "bin/drone_agent"), "--id", "0", "--port", str(tcp),
                                      "--sync-port", str(sync), "--multicast", f"{GROUP}:{mcast}"],
                                     stdout=subprocess.DEVNULL)
            while "trigger" not in frames:
                data, _ = receiver.recvfrom(64)
                if data[3] == 7:
                    frames["trigger"] = describe(data)
            agent.wait(timeout=10)
        finally:
            gcs.terminate()
            gcs.wait()
    out = ROOT / "evidence" / "frames.json"
    out.write_text(json.dumps(frames, indent=1))
    for name, frame in frames.items():
        print(name, frame)


if __name__ == "__main__":
    main()
