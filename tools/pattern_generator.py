#!/usr/bin/env python3
"""Sinh kịch bản trình diễn cho đàn drone: Ngôi sao 5 cánh -> Vòng xoắn ốc, LED RGB đổi màu.

Trình tự: cất cánh từ lưới mặt đất -> xếp ngôi sao (dải cầu vồng chạy quanh sao)
-> chuyển sang vòng xoắn ốc đang xoay (dải màu trượt theo chiều cao) -> hạ cánh, tắt đèn.

Đầu ra: mỗi drone một khung MSG_SHOW_WAYPOINT_DATA (common/protocol.h), ghép liên tiếp.
  payload = u16 drone_id, u16 knot_count, rồi knot_count mốc 31 byte:
            u32 t_ms, f32 x y z (NED, m), f32 vx vy vz (m/s), u8 r g b
  Mọi trường big-endian như phần còn lại của giao thức. Hai mốc liền nhau là một đoạn
  Cubic Hermite (waypoint_knot_t trong common/spline.h); màu LED nội suy tuyến tính.

Chạy: python3 -I tools/pattern_generator.py --drones 20 --output show_waypoints.bin
"""
import argparse
import binascii
import colorsys
import itertools
import json
import math
import pathlib
import struct
import sys
from typing import NamedTuple

MSG_SHOW_WAYPOINT_DATA = 10
HEADER_SIZE = 16
PAYLOAD_MAX = 65536
KNOT_FORMAT = struct.Struct(">I6f3B")  # 31 byte

GEOFENCE_XY = 50.0   # |x|, |y| <= 50 m, cùng hộp geofence dùng trong tests/test_failsafe.c
GEOFENCE_ALT = 50.0  # -50 <= z <= 0 (NED: z âm là độ cao)
MAX_SPEED = 3.0      # m/s, tốc độ đỉnh khi chuyển đội hình
SPIN_SPEED = 2.0     # m/s, tốc độ tiếp tuyến tối đa khi vòng xoắn xoay
STEP = 0.5           # s, khoảng cách giữa các mốc khi giữ đội hình hoặc xoay
STAR_ALT = 20.0
HELIX_BASE_ALT = 10.0
STAR_HOLD = 8.0
HELIX_SPIN = 16.0
SPIN_RAMP = 3.0
GROUND_RGB = (40, 40, 40)
OFF_RGB = (0, 0, 0)


class Knot(NamedTuple):
    t: float
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    rgb: tuple


class Helix(NamedTuple):
    per_turn: int
    radius: float
    pitch: float
    omega: float


def hsv(hue: float) -> tuple:
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, 1.0, 1.0)
    return (round(r * 255), round(g * 255), round(b * 255))


def min_distance(points) -> float:
    return min(math.dist(a, b) for a, b in itertools.combinations(points, 2))


def ground_grid(n: int, spacing: float) -> list:
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return [((i // cols - (rows - 1) / 2) * spacing, (i % cols - (cols - 1) / 2) * spacing, 0.0)
            for i in range(n)]


def star_corners() -> list:
    """10 đỉnh ngôi sao 5 cánh bán kính 1, xen kẽ mũi nhọn/đỉnh lõm, mũi đầu hướng Bắc (+x)."""
    inner = math.sin(math.radians(18)) / math.sin(math.radians(54))
    return [((1.0 if k % 2 == 0 else inner) * math.cos(k * math.pi / 5),
             (1.0 if k % 2 == 0 else inner) * math.sin(k * math.pi / 5)) for k in range(10)]


CORNER_ORDER = (0, 2, 4, 6, 8, 1, 5, 9, 3, 7)  # 5 mũi nhọn trước, rồi các đỉnh lõm rải đều
EDGE_ORDER = (0, 9, 4, 3, 8, 7, 2, 1, 6, 5)    # thêm drone theo từng cặp cạnh của một cánh


def star_formation(n: int, spacing: float):
    """Đặt n drone lên viền ngôi sao (nằm ngang ở STAR_ALT), luôn chiếm các đỉnh trước để
    giữ mũi nhọn, phần còn lại chia đều trên các cạnh. Phóng to sao cho hai drone gần nhất
    cách nhau đúng spacing. Trả về (vị trí, pha 0..1 dọc chu vi để tô màu)."""
    corners = star_corners()
    edges = [math.dist(corners[k], corners[(k + 1) % 10]) for k in range(10)]
    if n < 10:
        stations = [(k, 0.0) for k in sorted(CORNER_ORDER[:n])]
    else:
        extra = [(n - 10) // 10] * 10
        for k in EDGE_ORDER[:(n - 10) % 10]:
            extra[k] += 1
        stations = [(k, j / (extra[k] + 1)) for k in range(10) for j in range(extra[k] + 1)]
    unit, phase = [], []
    for k, f in stations:
        (ax, ay), (bx, by) = corners[k], corners[(k + 1) % 10]
        unit.append((ax + f * (bx - ax), ay + f * (by - ay)))
        phase.append((sum(edges[:k]) + f * edges[k]) / sum(edges))
    scale = spacing / min_distance(unit)
    return [(x * scale, y * scale, -STAR_ALT) for x, y in unit], phase


def helix_shape(n: int, spacing: float) -> Helix:
    """Vòng xoắn trục thẳng đứng: hai drone kề nhau cách nhau spacing, hai vòng cách nhau 2*spacing."""
    per_turn = max(5, math.ceil(n / 3))
    radius = spacing / (2 * math.sin(math.pi / per_turn))
    return Helix(per_turn, radius, 2 * spacing, min(0.5, SPIN_SPEED / radius))


def spin_angle(helix: Helix, tau: float):
    """Góc đã xoay (rad) và tốc độ góc (rad/s) sau tau giây: tăng tốc mượt, quay đều, giảm tốc mượt."""
    w, ramp = helix.omega, SPIN_RAMP

    def ramp_up(t):
        u = t / ramp
        return w * ramp * (u ** 3 - u ** 4 / 2), w * (3 * u * u - 2 * u ** 3)

    if tau <= ramp:
        return ramp_up(tau)
    if tau >= HELIX_SPIN - ramp:
        angle, rate = ramp_up(HELIX_SPIN - tau)
        return w * (HELIX_SPIN - ramp) - angle, rate
    return w * ramp / 2 + w * (tau - ramp), w


def helix_state(helix: Helix, slot: int, tau: float):
    """Vị trí và vận tốc chính xác của vị trí thứ slot trên vòng xoắn tại thời điểm tau."""
    angle, rate = spin_angle(helix, tau)
    theta = 2 * math.pi * slot / helix.per_turn + angle
    c, s = math.cos(theta), math.sin(theta)
    z = -(HELIX_BASE_ALT + helix.pitch * slot / helix.per_turn)
    return ((helix.radius * c, helix.radius * s, z),
            (-helix.radius * rate * s, helix.radius * rate * c, 0.0))


def assign(starts: list, goals: list) -> list:
    """Thuật toán Hungarian O(n^3): gán drone -> vị trí đích, tối thiểu tổng bình phương quãng đường.
    Kết hợp bay thẳng đồng bộ, cách gán này đảm bảo hai drone luôn cách nhau ít nhất
    min(khoảng cách đầu, khoảng cách đích) / sqrt(2) (Turpin et al., CAPT 2014)."""
    n = len(starts)
    cost = [[(a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2 for b in goals] for a in starts]
    u, v, owner, way = [0.0] * (n + 1), [0.0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for row in range(1, n + 1):
        owner[0], col = row, 0
        best, used = [math.inf] * (n + 1), [False] * (n + 1)
        while owner[col]:
            used[col] = True
            r, delta, nxt = owner[col], math.inf, 0
            for j in range(1, n + 1):
                if not used[j]:
                    reduced = cost[r - 1][j - 1] - u[r] - v[j]
                    if reduced < best[j]:
                        best[j], way[j] = reduced, col
                    if best[j] < delta:
                        delta, nxt = best[j], j
            for j in range(n + 1):
                if used[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                else:
                    best[j] -= delta
            col = nxt
        while col:
            prev = way[col]
            owner[col] = owner[prev]
            col = prev
    slots = [0] * n
    for j in range(1, n + 1):
        slots[owner[j] - 1] = j - 1
    return slots


def move_duration(distance: float) -> float:
    """Đoạn Hermite đứng yên -> đứng yên có tốc độ đỉnh 1.5 * distance / T."""
    return max(2.0, math.ceil(1.5 * distance / MAX_SPEED / STEP) * STEP)


def transition(show: list, goals: list, arrival_rgb):
    """Cả đàn cùng xuất phát, bay thẳng và cùng tới đích (đứng yên ở hai đầu)."""
    starts = [(k[-1].x, k[-1].y, k[-1].z) for k in show]
    slots = assign(starts, goals)
    longest = max(math.dist(starts[i], goals[slots[i]]) for i in range(len(show)))
    t_end = show[0][-1].t + move_duration(longest)
    for i, knots in enumerate(show):
        knots.append(Knot(t_end, *goals[slots[i]], 0.0, 0.0, 0.0, arrival_rgb(slots[i])))
    return t_end, slots


def steps(duration: float) -> list:
    return [STEP * k for k in range(1, round(duration / STEP) + 1)]


def build_show(n: int, spacing: float = 1.5) -> list:
    """Trả về danh sách mốc (Knot) cho từng drone, drone_id = chỉ số trong danh sách."""
    if not 5 <= n <= 100:
        raise ValueError("--drones phải trong khoảng 5..100")
    if not 0.5 <= spacing <= 10.0:
        raise ValueError("--spacing phải trong khoảng 0.5..10 m")
    pads = ground_grid(n, 2 * spacing)
    show = [[Knot(0.0, *pad, 0.0, 0.0, 0.0, GROUND_RGB)] for pad in pads]

    # Hình 1: ngôi sao 5 cánh, dải cầu vồng chạy vòng quanh chu vi
    star, phase = star_formation(n, spacing)
    t_star, star_slot = transition(show, star, lambda s: hsv(phase[s]))
    for tau in steps(STAR_HOLD):
        for i, knots in enumerate(show):
            slot = star_slot[i]
            knots.append(Knot(t_star + tau, *star[slot], 0.0, 0.0, 0.0, hsv(phase[slot] + 0.15 * tau)))

    # Hình 2: vòng xoắn ốc xoay quanh trục đứng, màu chuyển theo chiều cao và trượt theo thời gian
    helix = helix_shape(n, spacing)

    def helix_rgb(slot, tau):
        return hsv(0.55 + 0.35 * slot / (n - 1) + 0.08 * tau)

    start = [helix_state(helix, j, 0.0)[0] for j in range(n)]
    t_helix, helix_slot = transition(show, start, lambda s: helix_rgb(s, 0.0))
    for tau in steps(HELIX_SPIN):
        for i, knots in enumerate(show):
            position, velocity = helix_state(helix, helix_slot[i], tau)
            knots.append(Knot(t_helix + tau, *position, *velocity, helix_rgb(helix_slot[i], tau)))

    # Hạ cánh về lưới mặt đất, đèn tắt dần
    transition(show, pads, lambda s: OFF_RGB)

    for knots in show:
        for k in knots:
            if abs(k.x) > GEOFENCE_XY or abs(k.y) > GEOFENCE_XY or not -GEOFENCE_ALT <= k.z <= 0.0:
                raise ValueError("đội hình vượt geofence ±50 m / cao 50 m: giảm --spacing hoặc --drones")
    return show


def hermite(a: Knot, b: Knot, t: float):
    """Vị trí và vận tốc tại t, cùng công thức Cubic Hermite với common/spline.c."""
    h = b.t - a.t
    s = min(max((t - a.t) / h, 0.0), 1.0)
    s2, s3 = s * s, s * s * s
    position, velocity = [], []
    for p0, v0, p1, v1 in ((a.x, a.vx, b.x, b.vx), (a.y, a.vy, b.y, b.vy), (a.z, a.vz, b.z, b.vz)):
        position.append((2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * h * v0 +
                        (3 * s2 - 2 * s3) * p1 + (s3 - s2) * h * v1)
        velocity.append((6 * s2 - 6 * s) * (p0 - p1) / h + (3 * s2 - 4 * s + 1) * v0 +
                        (3 * s2 - 2 * s) * v1)
    return position, velocity


def trajectory(knots: list, dt: float) -> list:
    """Lấy mẫu (vị trí, vận tốc) mỗi dt giây từ t = 0 tới mốc cuối."""
    samples, i = [], 0
    for k in range(round(knots[-1].t / dt) + 1):
        t = k * dt
        while i < len(knots) - 2 and t > knots[i + 1].t:
            i += 1
        samples.append(hermite(knots[i], knots[i + 1], t))
    return samples


def analyze(show: list, dt: float = 0.1) -> dict:
    """Kiểm tra cả kịch bản đã nội suy: khoảng cách gần nhất, tốc độ lớn nhất, geofence."""
    min_separation, max_speed, inside = math.inf, 0.0, True
    for frame in zip(*(trajectory(knots, dt) for knots in show)):
        min_separation = min(min_separation, min_distance([p for p, _ in frame]))
        for (x, y, z), velocity in frame:
            max_speed = max(max_speed, math.hypot(*velocity))
            inside = inside and abs(x) <= GEOFENCE_XY and abs(y) <= GEOFENCE_XY and \
                -GEOFENCE_ALT <= z <= 1e-9
    return {"duration": show[0][-1].t, "min_separation": min_separation,
            "max_speed": max_speed, "inside_geofence": inside}


def encode_frame(msg_type: int, seq: int, payload: bytes) -> bytes:
    """Đóng khung giống encode() trong common/protocol.c (CRC-16/CCITT, bỏ qua byte 12..13)."""
    if len(payload) > PAYLOAD_MAX:
        raise ValueError("payload vượt PAYLOAD_MAX")
    header = struct.pack(">HBBIIHH", 0x5058, 1, msg_type, seq, len(payload), 0, 0)
    crc = binascii.crc_hqx(header + payload, 0xFFFF)
    return header[:12] + struct.pack(">H", crc) + header[14:] + payload


def encode_show(show: list) -> bytes:
    frames = []
    for drone_id, knots in enumerate(show):
        payload = struct.pack(">HH", drone_id, len(knots)) + b"".join(
            KNOT_FORMAT.pack(round(k.t * 1000), k.x, k.y, k.z, k.vx, k.vy, k.vz, *k.rgb) for k in knots)
        frames.append(encode_frame(MSG_SHOW_WAYPOINT_DATA, drone_id + 1, payload))
    return b"".join(frames)


def show_json(show: list, spacing: float) -> dict:
    return {"msg_type": MSG_SHOW_WAYPOINT_DATA, "drones": len(show), "spacing": spacing,
            "duration": show[0][-1].t,
            "trajectories": [{"drone_id": i, "knots": [
                {"t": k.t, "pos": [k.x, k.y, k.z], "vel": [k.vx, k.vy, k.vz], "rgb": list(k.rgb)}
                for k in knots]} for i, knots in enumerate(show)]}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Sinh kịch bản Ngôi sao 5 cánh -> Vòng xoắn ốc cho đàn drone")
    parser.add_argument("--drones", type=int, default=20, help="số drone, 5..100")
    parser.add_argument("--spacing", type=float, default=1.5,
                        help="khoảng cách giữa hai drone gần nhất trong đội hình (m)")
    parser.add_argument("--output", type=pathlib.Path, required=True,
                        help="tệp nhị phân chứa các khung MSG_SHOW_WAYPOINT_DATA")
    parser.add_argument("--json", type=pathlib.Path, help="ghi thêm bản JSON để xem/vẽ đồ thị")
    args = parser.parse_args(argv)
    try:
        show = build_show(args.drones, args.spacing)
    except ValueError as error:
        parser.error(str(error))
    report = analyze(show)
    if not report["inside_geofence"] or report["max_speed"] > MAX_SPEED + 1e-6 or \
            report["min_separation"] < args.spacing / math.sqrt(2) - 1e-6:
        sys.exit(f"kịch bản không an toàn, không ghi tệp: {report}")
    data = encode_show(show)
    args.output.write_bytes(data)
    if args.json:
        args.json.write_text(json.dumps(show_json(show, args.spacing), indent=1) + "\n", encoding="utf-8")
    print(f"{args.drones} drone, {report['duration']:.1f} s, {len(show[0])} mốc/drone, "
          f"gần nhất {report['min_separation']:.2f} m, nhanh nhất {report['max_speed']:.2f} m/s "
          f"-> {args.output} ({len(data)} byte)")


if __name__ == "__main__":
    main()
