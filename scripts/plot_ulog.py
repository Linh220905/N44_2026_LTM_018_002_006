#!/usr/bin/env python3
"""Plot the real PX4 SITL flight from a ULog (run with ~/px4-venv/bin/python -I).

Prints the statistics quoted in the report and saves evidence/hinh_ulog_flight.png.
"""
import pathlib
import gzip
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pyulog import ULog

LOG = pathlib.Path(__file__).resolve().parents[1] / "evidence/flight/02_36_09.ulg.gz"
OUT = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "hinh_ulog_flight.png"
OFFBOARD, LAND = 14, 18
plt.rcParams.update({"font.family": ["Times New Roman", "FreeSerif"], "font.size": 11, "axes.grid": True,
                     "axes.spines.top": False, "axes.spines.right": False})
ACT_X, ACT_Y, SETPT = "#2a78d6", "#eb6834", "#52514e"


def main(path: pathlib.Path) -> None:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        log = ULog(stream, ["vehicle_local_position", "vehicle_local_position_setpoint", "vehicle_status"])
    data = {d.name: d.data for d in log.data_list if d.multi_id == 0}
    t0 = log.start_timestamp
    pos, sp, st = data["vehicle_local_position"], data["vehicle_local_position_setpoint"], data["vehicle_status"]
    t_pos, t_sp, t_st = [(x["timestamp"] - t0) / 1e6 for x in (pos, sp, st)]
    t_off = t_st[np.argmax(st["nav_state"] == OFFBOARD)]
    t_land = t_st[np.argmax(st["nav_state"] == LAND)]
    t_end = t_st[np.where(np.diff(st["arming_state"]) != 0)[0][-1] + 1]
    window = (t_pos >= t_off - 3) & (t_pos <= t_end + 1)
    sp_idx = np.clip(np.searchsorted(t_sp, t_pos), 0, len(t_sp) - 1)
    sp_xyz = np.c_[sp["x"][sp_idx], sp["y"][sp_idx], sp["z"][sp_idx]]
    xyz = np.c_[pos["x"], pos["y"], pos["z"]]
    err = np.linalg.norm(xyz - sp_xyz, axis=1)
    offb = (t_pos >= t_off) & (t_pos < t_land)
    # sitl_flight.py holds each commanded waypoint 5 s; measure error in the last 0.5 s of each hold
    waypoints = np.array([(0, 0, -2), (2, 0, -2), (2, 2, -2), (0, 0, -2)], float)
    steady = []
    for k, wp in enumerate(waypoints, 1):
        hold = (t_pos > t_off + 5 * k - 0.5) & (t_pos <= t_off + 5 * k)
        steady.append(np.linalg.norm(xyz[hold] - wp, axis=1).mean())
    valid = offb & np.all(np.isfinite(sp_xyz), axis=1)
    print(f"log={path.name} duration_s={t_pos[-1]:.1f} position_samples={len(t_pos)} setpoint_samples={len(t_sp)}")
    print(f"offboard_s={t_off:.2f} land_s={t_land:.2f} disarm_s={t_end:.2f} offboard_duration_s={t_land - t_off:.1f}")
    print(f"position_rate_hz={len(t_pos) / t_pos[-1]:.1f} max_altitude_m={-xyz[offb, 2].min():.3f}")
    print(f"end_of_hold_err_cm={[round(100 * float(e), 1) for e in steady]} mean={100 * np.mean(steady):.1f}")
    print(f"tracking_err_vs_px4_setpoint_cm mean={100 * err[valid].mean():.1f} max={100 * err[valid].max():.1f}")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    t = t_pos[window] - t_off
    for ax, (label, i) in zip(axes[:2], [("Độ cao (m)", 2), ("Vị trí x, y (m)", None)]):
        if i == 2:
            ax.plot(t, -xyz[window, 2], color=ACT_X, lw=2, label="PX4 EKF2 (thực tế)")
            ax.plot(t, -sp_xyz[window, 2], color=SETPT, ls="--", lw=1.4, label="Điểm đặt")
        else:
            ax.plot(t, xyz[window, 0], color=ACT_X, lw=2, label="x thực tế")
            ax.plot(t, sp_xyz[window, 0], color=ACT_X, ls="--", lw=1.2, alpha=0.75, label="x điểm đặt")
            ax.plot(t, xyz[window, 1], color=ACT_Y, lw=2, label="y thực tế")
            ax.plot(t, sp_xyz[window, 1], color=ACT_Y, ls="--", lw=1.2, alpha=0.75, label="y điểm đặt")
        ax.set_xlabel("Thời gian kể từ khi vào OFFBOARD (s)")
        ax.set_ylabel(label)
        ax.legend(fontsize=9, frameon=False)
    axes[0].set_title("(a) Cất cánh, giữ 2 m và hạ cánh")
    axes[1].set_title("(b) Bám 4 điểm mốc theo phương ngang")
    axes[2].plot(xyz[offb, 1], xyz[offb, 0], color=ACT_X, lw=2, label="Quỹ đạo thực tế")
    axes[2].plot(waypoints[:, 1], waypoints[:, 0], "s", color=ACT_Y, ms=9, mfc="white", mew=2, label="Điểm mốc")
    axes[2].set_xlabel("y — Đông (m)")
    axes[2].set_ylabel("x — Bắc (m)")
    axes[2].set_title("(c) Quỹ đạo nhìn từ trên xuống")
    axes[2].set_aspect("equal", adjustable="datalim")
    axes[2].legend(fontsize=9, frameon=False)
    for ax in axes:
        ax.grid(True, color="#e4e3df", lw=0.7)
    fig.tight_layout()
    fig.savefig(OUT, dpi=220, facecolor="white")
    print("saved", OUT)


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else LOG)
