#!/usr/bin/env python3
"""Evaluation charts from evidence/results.json (measured, see evaluate_baseline.py)."""
import json
import pathlib
import statistics
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
plt.rcParams.update({"font.family": ["Times New Roman", "FreeSerif"], "font.size": 12, "axes.grid": True,
                     "grid.color": "#e4e3df", "grid.linewidth": 0.7, "axes.edgecolor": "#8a8984",
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
# validated categorical pair (light surface): slot 2 orange = baseline, slot 1 blue = proposed;
# markers and dash styles stay distinct so the charts also read in grayscale print
BASE_C, PROP_C, THEORY_C = "#eb6834", "#2a78d6", "#52514e"
BASE = dict(color=BASE_C, marker="o", ls="-", lw=2, ms=7, mfc="white", mew=1.8, capsize=3)
PROP = dict(color=PROP_C, marker="s", ls="--", lw=2, ms=7, mfc=PROP_C, capsize=3)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(EVIDENCE / name, dpi=220, facecolor="white")
    plt.close(fig)


def means(rows, key):
    return [r[key]["mean"] for r in rows], [r[key]["sd"] for r in rows]


def skew_vs_n(tn1):
    n = [r["N"] for r in tn1]
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    ax.errorbar(n, *means(tn1, "base_skew_ms"), label="Baseline (unicast tuần tự)", **BASE)
    ax.errorbar(n, *means(tn1, "prop_skew_ms"), label="Đề xuất (multicast + đồng bộ Cristian)", **PROP)
    ax.set_xlabel("Quy mô đàn N (drone)")
    ax.set_ylabel("Độ lệch khởi động σ_start (ms)")
    ax.legend(frameon=False)
    save(fig, "hinh_skew_vs_n.png")


def bandwidth_vs_n(tn1):
    n = [r["N"] for r in tn1]
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    ax.errorbar(n, *means(tn1, "base_bw_Bps"), label="Baseline: 41 B × 10 Hz × N", **BASE)
    ax.errorbar(n, *means(tn1, "prop_bw_Bps"), label="Đề xuất: heartbeat 16 B × 4 Hz", **PROP)
    ax.set_yscale("log")
    ax.set_xlabel("Quy mô đàn N (drone)")
    ax.set_ylabel("Băng thông chiều xuống B (byte/s, thang log)")
    ax.legend(frameon=False)
    save(fig, "hinh_bandwidth_vs_n.png")


def error_vs_loss(tn3):
    p = [r["p_loss"] for r in tn3]
    fig, ax = plt.subplots(figsize=(7.5, 4.3))

    ax.errorbar(p, *means(tn3, "base_e_rms_cm"), label="Baseline — đo", **BASE)
    ax.plot(p, [r["theory_rms_cm"] for r in tn3], color=THEORY_C, ls=":", lw=2, label="Baseline — lý thuyết E_RMS (4.14)")
    ax.plot(p, [r["prop_e_rms_cm"] for r in tn3], color=PROP_C, marker="s", ls="--", lw=2, ms=7,
            label="Đề xuất — đo")
    ax.set_xlabel("Tỷ lệ mất gói p_loss (%)")
    ax.set_ylabel("Sai số vị trí E_RMS (cm)")
    ax.legend(frameon=False)
    save(fig, "hinh_error_vs_loss.png")


def skew_vs_jitter(tn2):
    j = [r["jitter_ms"] for r in tn2]
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    ax.errorbar(j, *means(tn2, "base_skew_ms"), label="Baseline", **BASE)
    ax.errorbar(j, *means(tn2, "prop_skew_ms"), label="Đề xuất", **PROP)
    ax.set_xlabel("Trễ hàng đợi trung bình một chiều (ms)")
    ax.set_ylabel("Độ lệch khởi động σ_start (ms)")
    ax.legend(frameon=False)
    save(fig, "hinh_skew_vs_jitter.png")


def filter_box(tn4, jitter):
    data = tn4[jitter]
    ks = sorted(data, key=int)
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    pos_min = [i * 3 + 1 for i in range(len(ks))]
    pos_avg = [i * 3 + 2 for i in range(len(ks))]
    style = dict(widths=0.8, patch_artist=True, showfliers=False, medianprops=dict(color="black"))
    b1 = ax.boxplot([data[k]["mean"] for k in ks], positions=pos_min, **style)
    b2 = ax.boxplot([data[k]["min_rtt"] for k in ks], positions=pos_avg, **style)
    for patch in b1["boxes"]:
        patch.set(facecolor="#fbe1d6", edgecolor=BASE_C, linewidth=1.5)
    for patch in b2["boxes"]:
        patch.set(facecolor="#d5e4f7", edgecolor=PROP_C, linewidth=1.5)
    for group, color in ((b1, BASE_C), (b2, PROP_C)):
        for key in ("whiskers", "caps", "medians"):
            for line in group[key]:
                line.set(color=color, linewidth=1.5)
    ax.set_xticks([i * 3 + 1.5 for i in range(len(ks))], [f"K = {k}" for k in ks])
    ax.axhline(0, color=THEORY_C, lw=0.9)
    ax.set_ylabel("Sai số ước lượng θ̂ − θ (ms)")
    ax.legend([b1["boxes"][0], b2["boxes"][0]], ["Trung bình K mẫu", "Chọn mẫu RTT nhỏ nhất (đề xuất)"],
              frameon=False)
    save(fig, "hinh_clock_filter.png")


def filter_stats(tn4):
    out = {}
    for jitter, per_k in tn4.items():
        out[jitter] = {k: {m: {"mean_abs": statistics.fmean(abs(x) for x in v), "sd": statistics.stdev(v),
                               "n": len(v)} for m, v in d.items()} for k, d in per_k.items()}
    return out


def main(path: pathlib.Path) -> None:
    r = json.loads(path.read_text())
    skew_vs_n(r["tn1"])
    bandwidth_vs_n(r["tn1"])
    error_vs_loss(r["tn3"])
    skew_vs_jitter(r["tn2"])
    filter_box(r["tn4"], "5" if "5" in r["tn4"] else next(iter(r["tn4"])))
    print(json.dumps(filter_stats(r["tn4"]), indent=1))


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else EVIDENCE / "results.json")
