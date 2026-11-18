"""Kiểm tra kịch bản Ngôi sao -> Vòng xoắn ốc; chạy: python3 -I tests/test_pattern_generator.py"""
import importlib.util
import math
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "pattern_generator.py"
spec = importlib.util.spec_from_file_location("pattern_generator", SCRIPT)
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)


def crc16(data: bytes) -> int:
    """CRC-16/CCITT viết lại độc lập theo src/common/protocol.c (byte 12..13 tính là 0)."""
    value = 0xFFFF
    for i, byte in enumerate(data):
        value ^= (0 if i in (12, 13) else byte) << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021 if value & 0x8000 else value << 1) & 0xFFFF
    return value


def parse_frames(data: bytes) -> list:
    """Giải mã chuỗi khung MSG_SHOW_WAYPOINT_DATA thành [(seq, drone_id, [knot...])]."""
    frames, offset = [], 0
    while offset < len(data):
        magic, version, msg_type, seq, length, crc, reserved = struct.unpack_from(">HBBIIHH", data, offset)
        frame = data[offset:offset + 16 + length]
        assert (magic, version, msg_type, reserved) == (0x5058, 1, 10, 0)
        assert len(frame) == 16 + length and crc == crc16(frame)
        drone_id, count = struct.unpack_from(">HH", frame, 16)
        assert length == 4 + 31 * count
        knots = [struct.unpack_from(">I6f3B", frame, 20 + 31 * k) for k in range(count)]
        frames.append((seq, drone_id, knots))
        offset += 16 + length
    return frames


class PatternGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shows = {n: pg.build_show(n) for n in (5, 7, 20, 100)}

    def test_cli_writes_dlsp_frames_one_per_drone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory, "show.bin")
            result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--drones", "12",
                                     "--output", str(output), "--json", str(output.with_suffix(".json"))],
                                    capture_output=True, text=True, check=True)
            self.assertIn("12 drone", result.stdout)
            frames = parse_frames(output.read_bytes())
            self.assertTrue(output.with_suffix(".json").stat().st_size > 0)
        self.assertEqual([(seq, drone) for seq, drone, _ in frames], [(i + 1, i) for i in range(12)])
        show = pg.build_show(12)
        for (_, drone, knots), expected in zip(frames, show):
            self.assertEqual(len(knots), len(expected))
            for packed, knot in zip(knots, expected):
                self.assertEqual(packed[0], round(knot.t * 1000))
                for got, want in zip(packed[1:7], knot[1:7]):
                    self.assertAlmostEqual(got, want, places=4)  # float32
                self.assertEqual(packed[7:], knot.rgb)

    def test_rejects_invalid_arguments(self) -> None:
        for args in (["--drones", "4"], ["--drones", "101"], ["--drones", "100", "--spacing", "3"]):
            with tempfile.TemporaryDirectory() as directory:
                output = pathlib.Path(directory, "show.bin")
                result = subprocess.run([sys.executable, "-I", str(SCRIPT), *args, "--output", str(output)],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, args)
                self.assertFalse(output.exists(), args)

    def test_knots_are_time_ordered_and_synchronised(self) -> None:
        for n, show in self.shows.items():
            times = [k.t for k in show[0]]
            self.assertTrue(all(b > a for a, b in zip(times, times[1:])), n)
            for knots in show:
                self.assertEqual([k.t for k in knots], times)
                self.assertEqual(knots[0][4:7], (0.0, 0.0, 0.0))  # cất cánh từ đứng yên
                self.assertEqual(knots[-1][4:7], (0.0, 0.0, 0.0))
                self.assertEqual(knots[-1].z, 0.0)                 # hạ cánh xuống đất
                self.assertEqual(knots[-1].rgb, pg.OFF_RGB)

    def test_interpolated_show_is_safe(self) -> None:
        for n, show in self.shows.items():
            report = pg.analyze(show, dt=0.05)
            self.assertTrue(report["inside_geofence"], n)
            self.assertLessEqual(report["max_speed"], pg.MAX_SPEED + 1e-6, n)
            self.assertGreaterEqual(report["min_separation"], 1.5 / math.sqrt(2), n)

    def test_trajectory_is_c1_at_every_knot(self) -> None:
        for knots in self.shows[20][:5]:
            for a, b, c in zip(knots, knots[1:], knots[2:]):
                left_p, left_v = pg.hermite(a, b, b.t)
                right_p, right_v = pg.hermite(b, c, b.t)
                for k in range(3):
                    self.assertAlmostEqual(left_p[k], right_p[k], places=12)
                    self.assertAlmostEqual(left_v[k], right_v[k], places=12)

    def star_knots(self, show: list) -> list:
        index = next(i for i, k in enumerate(show[0]) if k.z == -pg.STAR_ALT)
        return [knots[index] for knots in show]

    def test_star_has_five_points(self) -> None:
        for n in (5, 7, 20, 100):
            star = self.star_knots(self.shows[n])
            radius = [math.hypot(k.x, k.y) for k in star]
            tip = max(radius)
            tips = sorted(math.degrees(math.atan2(k.y, k.x)) % 360
                          for k, r in zip(star, radius) if r > tip - 1e-6)
            self.assertEqual(len(tips), 5, n)
            for angle, expected in zip(tips, range(0, 360, 72)):
                self.assertAlmostEqual(angle, expected, places=6)
            # mọi drone nằm trên viền sao: ngoài đỉnh lõm, trong mũi nhọn
            inner = tip * math.sin(math.radians(18)) / math.sin(math.radians(54))
            self.assertTrue(all(inner * math.cos(math.radians(36)) - 1e-6 <= r <= tip + 1e-6 for r in radius))
            self.assertTrue(all(k.z == -pg.STAR_ALT for k in star))

    def test_helix_rises_and_spins(self) -> None:
        show = self.shows[20]
        helix = pg.helix_shape(20, 1.5)
        first = next(i for i, k in enumerate(show[0]) if k.z != -pg.STAR_ALT and k.t > 10 and
                     abs(math.hypot(k.x, k.y) - helix.radius) < 1e-9)
        middle = first + round(pg.HELIX_SPIN / 2 / pg.STEP)
        layer = [knots[first] for knots in show]
        heights = sorted(-k.z for k in layer)
        self.assertGreater(heights[-1] - heights[0], 2 * helix.pitch * 0.9)  # cao gần 3 vòng
        for knots in show:
            self.assertAlmostEqual(math.hypot(knots[middle].x, knots[middle].y), helix.radius, places=9)
            speed = math.hypot(knots[middle].vx, knots[middle].vy)
            self.assertAlmostEqual(speed, helix.radius * helix.omega, places=9)
            self.assertEqual(knots[middle].z, knots[first].z)  # xoay ngang, giữ độ cao

    def test_led_colours_change_over_time(self) -> None:
        for knots in self.shows[20]:
            colours = [k.rgb for k in knots]
            self.assertGreater(len(set(colours)), 20)
            self.assertTrue(all(0 <= c <= 255 for rgb in colours for c in rgb))
        star = self.star_knots(self.shows[20])
        self.assertEqual(len({k.rgb for k in star}), 20)  # cầu vồng: mỗi drone một màu

    def test_frame_encoding_matches_protocol(self) -> None:
        frame = pg.encode_frame(10, 7, b"\x00\x2a")
        self.assertEqual(frame[:4], b"PX\x01\x0a")
        self.assertEqual(struct.unpack(">H", frame[12:14])[0], crc16(frame))
        with self.assertRaises(ValueError):
            pg.encode_frame(10, 1, bytes(pg.PAYLOAD_MAX + 1))


if __name__ == "__main__":
    unittest.main()
