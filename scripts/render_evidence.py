#!/usr/bin/env python3
"""Render real captured text (terminal logs, DLSP frames) into black-and-white report figures."""
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "evidence"
MONO = "DejaVu Sans Mono"
matplotlib.rcParams["text.parse_math"] = False  # log lines contain literal $


def terminal(src: str, out: str, width_chars: int = 118) -> None:
    lines = [line[:width_chars] for line in (EVIDENCE / src).read_text().splitlines()]
    fig = plt.figure(figsize=(width_chars * 0.075, 0.24 * len(lines) + 0.35))
    for i, line in enumerate(lines):
        fig.text(0.012, 1 - (i + 0.8) / (len(lines) + 0.6), line, family=MONO, fontsize=9,
                 weight="bold" if line.startswith("$") else "normal", va="center")
    fig.patches.append(plt.Rectangle((0.002, 0.004), 0.996, 0.992, transform=fig.transFigure,
                                     fill=False, ec="black", lw=1))
    fig.savefig(EVIDENCE / out, dpi=220, facecolor="white")
    plt.close(fig)


def frames(out: str) -> None:
    data = json.loads((EVIDENCE / "frames.json").read_text())
    titles = {"heartbeat": "(a) MSG_SWARM_HEARTBEAT nhận từ nhóm 239.255.0.1",
              "time_sync_req": "(b) MSG_TIME_SYNC_REQ gửi tới Time Server (UDP unicast)",
              "time_sync_resp": "(c) MSG_TIME_SYNC_RESP trả về T1, T2, T3",
              "trigger": "(d) MSG_SHOW_ARM_TRIGGER nhận từ nhóm 239.255.0.1"}
    rows = []
    for key, title in titles.items():
        frame = data[key]
        raw = frame["hex"].split()
        rows.append(("title", title))
        for off in range(0, len(raw), 16):
            rows.append(("hex", f"{off:04x}  " + " ".join(raw[off:off + 16])))
        rows.append(("info", f"magic={frame['magic']} ver={frame['version']} type={frame['type']} seq={frame['seq']} "
                             f"len={frame['payload_len']} crc={frame['checksum']} ({'đúng' if frame['crc_ok'] else 'SAI'})"))
        rows.append(("gap", ""))
    fig = plt.figure(figsize=(9.6, 0.25 * len(rows) + 0.3))
    for i, (kind, text) in enumerate(rows):
        fig.text(0.015, 1 - (i + 0.8) / (len(rows) + 0.5), text, va="center",
                 family="FreeSerif" if kind == "title" else MONO,
                 fontsize=11 if kind == "title" else 9, weight="bold" if kind == "title" else "normal")
    fig.patches.append(plt.Rectangle((0.002, 0.004), 0.996, 0.992, transform=fig.transFigure,
                                     fill=False, ec="black", lw=1))
    fig.savefig(EVIDENCE / out, dpi=220, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    terminal("run_make_test.txt", "hinh_make_test.png", 92)
    terminal("run_swarm4.txt", "hinh_run_swarm4.png", 118)
    frames("hinh_frames.png")
    print("saved")
