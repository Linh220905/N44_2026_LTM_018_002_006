#!/usr/bin/env python3
"""Generate a tiny versioned show: SHOW + uint16 count + fixed 25-byte records."""
import argparse
import math
import pathlib
import struct


def generate(count: int, shape: str) -> bytes:
    if not 1 <= count <= 100:
        raise ValueError("--drones must be 1..100")
    records = []
    for drone_id in range(count):
        angle = 2 * math.pi * drone_id / count
        if shape == "heart":
            x = 16 * math.sin(angle) ** 3 / 8
            y = (13 * math.cos(angle) - 5 * math.cos(2 * angle)
                 - 2 * math.cos(3 * angle) - math.cos(4 * angle)) / 8
        else:
            radius = 2 if drone_id % 2 == 0 else 0.9
            x, y = radius * math.cos(angle), radius * math.sin(angle)
        records.append(struct.pack(">HIffffBBB", drone_id, 0, x, y, 2.0, 0.0,
                                   255, 30, 100))
    return b"SHOW" + struct.pack(">H", count) + b"".join(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drones", type=int, default=100)
    parser.add_argument("--shape", choices=("heart", "star"), default="heart")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    args.output.write_bytes(generate(args.drones, args.shape))


if __name__ == "__main__":
    main()
