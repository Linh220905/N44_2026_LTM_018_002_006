#!/usr/bin/env python3
"""Draw report block diagrams / flowcharts (Hình 1-10) into evidence/diagrams/."""
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon

OUT = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "diagrams"
plt.rcParams.update({"font.family": ["FreeSerif", "Noto Serif"], "font.size": 13})
NAVY, BLUE, GREEN, ORANGE, RED, GREY = "black", "white", "white", "white", "white", "white"  # black & white only


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w * 10)
    ax.set_ylim(0, h * 10)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fc=BLUE, ec=NAVY, size=11, bold=False, style="round,pad=0.02,rounding_size=1.2"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, fc=fc, ec=ec, lw=1.3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
            fontweight="bold" if bold else "normal", linespacing=1.25)


def diamond(ax, cx, cy, w, h, text, size=10):
    ax.add_patch(Polygon([(cx - w / 2, cy), (cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2)],
                         fc=ORANGE, ec=NAVY, lw=1.3))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=size, linespacing=1.15)


def arrow(ax, a, b, text="", both=False, color=NAVY, style="-", size=12, offset=(0, 1.2), rad=0.0):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="<|-|>" if both else "-|>", mutation_scale=14,
                                 color=color, lw=1.3, linestyle=style,
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((a[0] + b[0]) / 2 + offset[0], (a[1] + b[1]) / 2 + offset[1], text, ha="center",
                va="bottom", fontsize=size, color=color,
                bbox=dict(fc="white", ec="none", pad=0.6))


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def architecture():
    fig, ax = canvas(13, 11)
    ax.set_xlim(0, 160)
    ax.set_ylim(0, 110)
    # tier 1
    ax.add_patch(FancyBboxPatch((3, 82), 154, 25, boxstyle="round,pad=0,rounding_size=2", fc="white", ec=NAVY, lw=1.5))
    ax.text(6, 103.5, "TẦNG 1 — ĐIỀU PHỐI: GCS Master Server (C, POSIX socket, epoll)", fontsize=14, fontweight="bold", color=NAVY)
    for i, (t, d) in enumerate([("Show Loader", "đọc show.bin\nkiểm tra định dạng"),
                                ("Session Manager", "TCP :8080, epoll\nHELLO / TRAJECTORY"),
                                ("Time Server", "UDP :9091\nđóng dấu T2, T3"),
                                ("Multicast Announcer", "239.255.0.1:9090\nHEARTBEAT / TRIGGER")]):
        box(ax, 6 + i * 37.5, 85, 35, 14, f"{t}\n{d}", size=13)
    # links
    arrow(ax, (33, 82), (33, 63), "TCP :8080 (tin cậy)\nHELLO, TRAJECTORY_DATA", both=True, offset=(0, -6))
    arrow(ax, (80, 82), (80, 63), "UDP unicast :9091\nTIME_SYNC_REQ/RESP", both=True, offset=(0, -6))
    arrow(ax, (127, 82), (127, 63), "UDP multicast\n4 Hz HEARTBEAT, TRIGGER", offset=(0, -6))
    # tier 2
    ax.add_patch(FancyBboxPatch((3, 33), 154, 30, boxstyle="round,pad=0,rounding_size=2", fc="white", ec="black", lw=1.5))
    ax.text(6, 59, "TẦNG 2 — THỰC THI PHÂN TÁN: N × Drone Agent (mỗi agent một tiến trình, socket và đồng hồ riêng)",
            fontsize=14, fontweight="bold", color="black")
    for i, t in enumerate(["Protocol Codec\nencode / decode\nCRC-16, big-endian", "Clock Discipline\nCristian 4 mốc\nlọc RTT nhỏ nhất",
                           "Trajectory Buffer\nquỹ đạo nạp vào RAM", "Failsafe + Geofence\nheartbeat 2000 ms\nhộp 3D, pin"]):
        box(ax, 6 + i * 37.5, 37, 35, 17, t, fc=GREEN, ec="black", size=13)
    # tier 3
    arrow(ax, (50, 33), (50, 18), "MAVLink v2 / UDP\n(minh họa 1 drone)", offset=(-1, -6))
    arrow(ax, (118, 33), (118, 18), "mô hình động học\nnội bộ", offset=(0, -6))
    ax.add_patch(FancyBboxPatch((3, 1), 154, 18.5, boxstyle="round,pad=0,rounding_size=2", fc="white", ec="black", lw=1.5))
    ax.text(6, 16.3, "TẦNG 3 — MÔ PHỎNG", fontsize=14, fontweight="bold", color="black")
    box(ax, 8, 2.5, 70, 11, "PX4 SITL v1.14.4 + jMAVSim\n+ QGroundControl 4.4.5", fc=ORANGE, ec="black", size=13)
    box(ax, 84, 2.5, 70, 11, "Mô hình x(t) = x0 + v·t\ncho N drone còn lại", fc=ORANGE, ec="black", size=13)
    save(fig, "h01_kien_truc.png")


def sequence():
    fig, ax = canvas(16, 12.5)
    ax.set_ylim(22, 125)
    xs = {"Agent i": 20, "GCS (TCP :8080)": 62, "Time Server (:9091)": 100, "Nhóm 239.255.0.1": 140}
    for name, x in xs.items():
        box(ax, x - 15, 116, 30, 7, name, bold=True, size=11)
        ax.plot([x, x], [26, 116], color="black", lw=1, ls="--", zorder=0)
    a, g, t, m = xs.values()
    y = 110

    def phase(label):
        nonlocal y
        ax.add_patch(FancyBboxPatch((3, y - 2.5), 154, 4.5, boxstyle="square,pad=0", fc="white", ec="black", lw=0.8, zorder=2))
        ax.text(5, y - 0.3, label, fontsize=11, fontweight="bold", color=NAVY, va="center", zorder=3)
        y -= 7

    def msg(x1, x2, text, dashed=False):
        nonlocal y
        arrow(ax, (x1, y), (x2, y), text, style="--" if dashed else "-", offset=(0, 0.6))
        y -= 7.5

    phase("PHA 1 — Bắt tay và nạp quỹ đạo (TCP, tin cậy)")
    msg(a, g, "MSG_HELLO_REQ (drone_id)")
    msg(g, a, "MSG_HELLO_ACK (drone_id)")
    msg(g, a, "MSG_TRAJECTORY_DATA (t, x, y, z, yaw, r, g, b)")
    phase("PHA 2 — Đồng bộ đồng hồ Cristian (UDP unicast, lặp K lần)")
    msg(a, t, "TIME_SYNC_REQ (T1)")
    msg(t, a, "TIME_SYNC_RESP (T1, T2, T3);   Agent ghi T4, chọn mẫu RTT nhỏ nhất")
    phase("PHA 3 — Kích hoạt đồng loạt (UDP multicast)")
    msg(m, a, "MSG_SHOW_ARM_TRIGGER (T_target, µs) — một gói cho cả nhóm, phát lặp 4 Hz tới T_target + 1 s")
    ax.text(a + 2, y + 2.2, "chờ tới khi đồng hồ đã hiệu chỉnh = T_target", fontsize=10, style="italic")
    y -= 3
    phase("PHA 4 — Thực thi phân tán (quỹ đạo lấy từ RAM)")
    msg(m, a, "MSG_SWARM_HEARTBEAT (16 byte, 4 Hz)", dashed=True)
    ax.text(a + 2, y + 2, "mất heartbeat > 2000 ms  ⇒  FAILSAFE (AUTO_HOVER)", fontsize=10, style="italic", color="black")
    save(fig, "h02_luong_du_lieu.png")


def frame_format():
    fig, ax = canvas(16, 5.6)
    fields = [("MAGIC\n0x5058", 2), ("VER\n0x01", 1), ("TYPE", 1), ("SEQ_NUM\n(u32)", 4),
              ("PAYLOAD_LEN\n(u32)", 4), ("CHECKSUM\nCRC-16", 2), ("RESERVED\n0x0000", 2)]
    unit, x = 8.4, 4
    colors = [BLUE, BLUE, BLUE, GREEN, GREEN, ORANGE, GREY]
    for (name, size), c in zip(fields, colors):
        box(ax, x, 26, unit * size, 14, name, fc=c, size=11, style="square,pad=0")
        ax.text(x + unit * size / 2, 42, f"{size} B", ha="center", fontsize=10, color="black")
        x += unit * size
    box(ax, x, 26, 17, 14, "PAYLOAD\n0…65536 B", fc="white", size=10, style="square,pad=0")
    for off in (0, 2, 3, 4, 8, 12, 14, 16):
        ax.text(4 + unit * off, 23.5, str(off), ha="center", fontsize=10, color="black")
    ax.annotate("", xy=(4, 18), xytext=(4 + unit * 16, 18), arrowprops=dict(arrowstyle="<->", color=NAVY))
    ax.text(4 + unit * 8, 13.5, "Header cố định 16 byte — mọi trường số nguyên là big-endian (htons / htonl)",
            ha="center", fontsize=11, color=NAVY)
    ax.text(4, 5, "CRC-16/CCITT-FALSE (đa thức 0x1021, giá trị đầu 0xFFFF) tính trên toàn khung, hai byte CHECKSUM coi là 0 khi tính.",
            fontsize=10.5)
    save(fig, "h03_khung_tin.png")


def baseline_arch():
    fig, ax = canvas(16, 7.5)
    box(ax, 55, 58, 50, 13, "GCS Baseline Server\ngiữ toàn bộ kịch bản, phát điểm đặt 10 Hz", bold=False, size=11)
    for i, x in enumerate([10, 50, 110]):
        label = f"Agent {i + 1}" if i < 2 else "Agent N"
        box(ax, x, 22, 34, 11, f"{label}\nchuyển tiếp điểm đặt", fc=GREEN, ec="black", size=10.5)
        box(ax, x + 4, 3, 26, 9, "PX4 / mô hình", fc=ORANGE, ec="black", size=10)
        arrow(ax, (80, 58), (x + 17, 33), "MSG_SETPOINT\n41 B × 10 Hz" if i == 0 else "")
        arrow(ax, (x + 17, 22), (x + 17, 12))
    ax.text(97, 27, "…", fontsize=24)
    ax.text(150, 45, "N luồng TCP độc lập\nGửi tuần tự i = 1 … N\nBăng thông ~ O(N)", fontsize=11, ha="right", color=NAVY)
    save(fig, "h04_baseline.png")


def four_timestamps():
    fig, ax = canvas(12, 7.5)
    ax.plot([25, 25], [11, 66], color=NAVY, lw=2)
    ax.plot([95, 95], [11, 66], color=NAVY, lw=2)
    box(ax, 10, 66, 30, 7, "Agent i (đồng hồ cục bộ)", bold=True, size=11)
    box(ax, 80, 66, 30, 7, "GCS (đồng hồ chủ)", bold=True, size=11)
    arrow(ax, (25, 55), (95, 42), "TIME_SYNC_REQ   (trễ d₁)", offset=(0, 1.5))
    arrow(ax, (95, 32), (25, 16), "TIME_SYNC_RESP   (trễ d₂)", offset=(0, 1.5))
    for x, y, t in [(20, 55, "T1"), (100, 42, "T2"), (100, 32, "T3"), (20, 16, "T4")]:
        ax.text(x, y, t, fontsize=13, fontweight="bold", ha="center", va="center", color="black")
    ax.text(106, 37, "xử lý", fontsize=10, style="italic", va="center")
    ax.text(60, 4, "θ̂ = [(T2 − T1) + (T3 − T4)] / 2        R = (T4 − T1) − (T3 − T2)        |θ̂ − θ| ≤ R / 2",
            ha="center", fontsize=11.5, color=NAVY)
    save(fig, "h05_bon_moc.png")


def fsm():
    fig, ax = canvas(16, 9.5)
    states = {"INIT": (8, 70), "CONNECTED": (42, 70), "LOADED": (76, 70), "SYNCED": (110, 70),
              "ARMED": (110, 38), "SHOW_RUNNING": (68, 38), "FAILSAFE": (26, 38), "FINISHED": (68, 8)}
    for s, (x, y) in states.items():
        fc = RED if s == "FAILSAFE" else (GREEN if s in ("SHOW_RUNNING", "FINISHED") else BLUE)
        box(ax, x, y, 28 if s != "SHOW_RUNNING" else 32, 11, s, fc=fc, bold=True, size=11)
    arrow(ax, (36, 75.5), (42, 75.5))
    ax.text(39, 84, "HELLO_ACK", ha="center", fontsize=10)
    arrow(ax, (70, 75.5), (76, 75.5)); ax.text(73, 84, "TRAJECTORY\n_DATA", ha="center", fontsize=10)
    arrow(ax, (104, 75.5), (110, 75.5)); ax.text(107, 84, "K mẫu sync\nchọn R nhỏ nhất", ha="center", fontsize=10)
    arrow(ax, (124, 70), (124, 49), "SHOW_ARM_TRIGGER\n(T_target)", offset=(17, -4))
    arrow(ax, (110, 43.5), (100, 43.5)); ax.text(105, 51, "đồng hồ\nđạt T_target", ha="center", fontsize=10)
    arrow(ax, (68, 43.5), (54, 43.5)); ax.text(61, 51, "mất HB > 2 s\ngeofence, pin < 10 %\nEMERGENCY_STOP", ha="center", fontsize=9.5)
    arrow(ax, (84, 38), (82, 19), "hết thời lượng\nshow", offset=(13, -3))
    ax.text(8, 60, "Lỗi trước khi bay (TCP đóng, quỹ đạo sai,\nđồng bộ thất bại, mất HB > 2 s):\nagent thoát, drone không cất cánh", fontsize=10, va="top")
    ax.text(40, 22, "FAILSAFE: AUTO_HOVER\n(MAV_CMD_DO_SET_MODE) hoặc\nMAV_CMD_NAV_LAND", fontsize=10, ha="center",
            color="black")
    save(fig, "h06_fsm.png")


def flow(name, steps, width=10, title_h=0):
    """Vertical flowchart. steps: list of (kind, text[, branch_text])."""
    h = 8 + 13 * len(steps)
    fig, ax = canvas(width, h / 10)
    cx, y = width * 5 - 15, h - 8
    for i, step in enumerate(steps):
        kind, text = step[0], step[1]
        if kind == "term":
            box(ax, cx - 16, y - 3, 32, 7, text, fc=GREY, bold=True, size=10.5, style="round,pad=0.02,rounding_size=3.5")
        elif kind == "dec":
            diamond(ax, cx, y + 0.5, 46, 10, text)
            if len(step) > 2:
                side_no = step[2].lower().startswith("không")
                label = step[2].split(":", 1)[1].strip() if step[2].lower().startswith(("có:", "không:")) else step[2]
                arrow(ax, (cx + 23, y + 0.5), (cx + 31, y + 0.5))
                ax.text(cx + 32, y + 0.5, label, fontsize=10, va="center")
                ax.text(cx + 24, y + 1.6, "Không" if side_no else "Có", fontsize=9,
                        color="black" if side_no else "black")
                ax.text(cx + 1.2, y - 6.2, "Có" if side_no else "Không", fontsize=9,
                        color="black" if side_no else "black")
        else:
            box(ax, cx - 22, y - 3.5, 44, 8, text, size=10)
        if i < len(steps) - 1:
            arrow(ax, (cx, y - 4.5), (cx, y - 8.6))
        y -= 13
    save(fig, name)
    return fig


def flowcharts():
    flow("h07_luu_do_gcs.png", [
        ("term", "Bắt đầu"),
        ("proc", "Đọc show.bin, kiểm tra 'SHOW', N ≤ 100"),
        ("proc", "Tạo socket TCP :8080 (non-blocking), UDP :9091,\nUDP multicast; đăng ký vào epoll"),
        ("proc", "epoll_wait(timeout = 50 ms)"),
        ("dec", "Sự kiện trên\nlistener?", "accept(), thêm fd vào epoll"),
        ("dec", "Sự kiện trên\nUDP :9091?", "ghi T2 → giải mã → ghi T3 → gửi RESP"),
        ("dec", "Dữ liệu TCP\ncủa agent?", "ghép đủ 18 B HELLO → gửi ACK + quỹ đạo"),
        ("dec", "Mọi agent đã\nnhận quỹ đạo?", "chốt T_target = now + 1,5 s"),
        ("dec", "Đến chu kỳ\n250 ms?", "multicast TRIGGER hoặc HEARTBEAT"),
        ("proc", "Quay lại epoll_wait (tới khi SIGTERM)"),
    ], width=11)
    flow("h08_luu_do_sync.png", [
        ("term", "Bắt đầu đồng bộ"),
        ("proc", "R_min ← +∞ ;  k ← 1"),
        ("proc", "T1 ← đồng hồ cục bộ; gửi TIME_SYNC_REQ(T1)"),
        ("dec", "Nhận RESP hợp lệ\ntrong 200 ms?", "không: bỏ mẫu, k ← k + 1"),
        ("proc", "T4 ← đồng hồ cục bộ; đọc T2, T3"),
        ("proc", "R_k = (T4−T1) − (T3−T2);  θ_k = [(T2−T1)+(T3−T4)]/2"),
        ("dec", "R_k < R_min ?", "có: R_min ← R_k, θ̂ ← θ_k"),
        ("dec", "k < K ?", "có: k ← k + 1, quay lại"),
        ("term", "Trả về θ̂, ε = R_min / 2"),
    ], width=11)
    flow("h09_luu_do_agent.png", [
        ("term", "Agent khởi động (--id i)"),
        ("proc", "Gia nhập nhóm multicast (IP_ADD_MEMBERSHIP)"),
        ("proc", "TCP connect → HELLO_REQ → nhận ACK + quỹ đạo"),
        ("proc", "Đồng bộ Cristian K mẫu → θ̂, ε"),
        ("proc", "poll() trên multicast và timerfd (200 ms)"),
        ("dec", "CRC đúng và\nseq mới?", "không: bỏ gói"),
        ("dec", "TRIGGER?", "không: cập nhật thời điểm HB"),
        ("proc", "Hẹn timerfd tuyệt đối: cục bộ + θ̂ = T_target"),
        ("proc", "SHOW_RUNNING: điểm đặt lấy từ RAM"),
        ("dec", "failsafe_check()\nvi phạm?", "có: AUTO_HOVER / LAND"),
        ("term", "Kết thúc show"),
    ], width=11)
    flow("h10_luu_do_baseline.png", [
        ("term", "Baseline server bắt đầu"),
        ("proc", "Chờ N agent HELLO (epoll), chỉ gửi ACK — không gửi quỹ đạo"),
        ("proc", "Gửi lệnh khởi động tuần tự i = 1 … N"),
        ("proc", "Mỗi 100 ms: tính x_i(t) = x0 + v·t cho từng i"),
        ("proc", "send() MSG_SETPOINT 41 B tới từng agent (N lần)"),
        ("dec", "Hết thời lượng?", "chưa: chờ chu kỳ kế"),
        ("proc", "Gửi EMERGENCY_STOP, in băng thông, CPU"),
        ("term", "Agent: mất gói ⇒ giữ điểm đặt cũ ⇒ sai số"),
    ], width=11)


if __name__ == "__main__":
    architecture()
    sequence()
    frame_format()
    baseline_arch()
    four_timestamps()
    fsm()
    flowcharts()
    print("saved", OUT)
