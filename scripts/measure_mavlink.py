#!/usr/bin/env python3
"""Estimate MAVLink sequence gaps on localhost. Not proof of network loss."""
import argparse
import collections
import select
import socket
import time

from pymavlink.dialects.v20 import all as dialect


def measure(port: int, seconds: float) -> tuple[int, int, int, dict[str, int]]:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    receiver.bind(("127.0.0.1", port))
    parser = dialect.MAVLink(None)
    parser.robust_parsing = True
    last: dict[tuple[int, int], int] = {}
    types: collections.Counter[str] = collections.Counter()
    received = missing = resets = 0
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            if not select.select([receiver], [], [], min(0.1, deadline - time.monotonic()))[0]:
                continue
            data, _ = receiver.recvfrom(65535)
            frames = parser.parse_buffer(data) or []
            for message in frames:
                if message.get_type() == "BAD_DATA":
                    continue
                raw = message.get_msgbuf()
                if raw[0] == 0xfd:  # MAVLink 2: seq, sysid, compid.
                    sequence, source = raw[4], (raw[5], raw[6])
                elif raw[0] == 0xfe:  # MAVLink 1.
                    sequence, source = raw[2], (raw[3], raw[4])
                else:
                    continue
                if source in last:
                    gap = (sequence - last[source] - 1) & 255
                    if gap <= 127:
                        missing += gap
                    else:
                        resets += 1  # Sequence reset or out of order.
                last[source] = sequence
                received += 1
                types[message.get_type()] += 1
    finally:
        receiver.close()
    return received, missing, resets, dict(types)


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate MAVLink sequence gaps on PX4 SITL UDP")
    parser.add_argument("--port", type=int, default=14540)
    parser.add_argument("--seconds", type=float, default=10)
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535 or not 0 < arguments.seconds <= 3600:
        parser.error("port must be 1..65535 and seconds must be in (0, 3600]")
    received, missing, resets, types = measure(arguments.port, arguments.seconds)
    if not received:
        parser.error("no MAVLink frames; start PX4 SITL before this receiver (and avoid competing listeners)")
    loss = 100 * missing / (received + missing)
    print(f"received={received} missing_estimate={missing} loss_estimate={loss:.2f}% "
          f"resets_or_reorder={resets} interval={arguments.seconds:g}s")
    print("messages:", ", ".join(f"{name}={count}" for name, count in sorted(types.items())))
    print("Note: estimate at this receiver, not proven network packet loss; "
          "UDP/MAVLink frame counts may differ. Use tcpdump on lo for raw packets.")


if __name__ == "__main__":
    main()
