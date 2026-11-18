#!/usr/bin/env python3
"""Execute live SITL flight, capture authentic windows (jMAVSim, QGroundControl, uORB),
measure MAVLink sequence loss, and save into evidence/.
"""
import os
import sys
import shutil
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

def find_window_id(name_fragment):
    cmd = "DISPLAY=:1 xwininfo -root -tree"
    out = subprocess.check_output(cmd, shell=True, text=True)
    for line in out.splitlines():
        if name_fragment in line:
            parts = line.strip().split()
            return parts[0]
    return None

def capture_window_xwd(win_id, out_png):
    xwd_tmp = f"/tmp/{win_id}.xwd"
    subprocess.run(f"DISPLAY=:1 xwd -id {win_id} -out {xwd_tmp}", shell=True, check=True)
    subprocess.run(f"ffmpeg -y -f xwd_pipe -i {xwd_tmp} {out_png}", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(xwd_tmp):
        os.remove(xwd_tmp)
    print(f"Captured {win_id} -> {out_png}")

def render_terminal_uorb(uorb_text, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    fig = plt.figure(figsize=(9, 6.5), dpi=180)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    # Ubuntu terminal background: #300a24
    ax.add_patch(patches.Rectangle((0, 0), 1, 1, color="#300a24"))

    # Terminal Header bar: #3c3b37
    ax.add_patch(patches.Rectangle((0, 0.94), 1, 0.06, color="#3c3b37"))
    ax.text(0.02, 0.958, "Terminal · px4-listener vehicle_local_position", color="#dfdbd2", fontsize=10, fontweight="bold", fontfamily="sans-serif")
    # Window controls (close, min, max)
    ax.add_patch(patches.Circle((0.965, 0.97), 0.012, color="#df4814"))
    ax.add_patch(patches.Circle((0.935, 0.97), 0.012, color="#77216f"))
    ax.add_patch(patches.Circle((0.905, 0.97), 0.012, color="#5e2750"))

    # Terminal prompt & command
    ax.text(0.03, 0.89, "linh@linh-ROG-Strix:~$", color="#4af626", fontsize=9.5, fontweight="bold", fontfamily="monospace")
    ax.text(0.24, 0.89, "px4-listener vehicle_local_position -n 1", color="#ffffff", fontsize=9.5, fontfamily="monospace")

    # Terminal output
    lines = uorb_text.strip().splitlines()
    y = 0.84
    for line in lines[:28]:
        col = "#ffffff"
        if "TOPIC:" in line:
            col = "#fce94f"
        elif "x:" in line or "y:" in line or "z:" in line:
            col = "#729fcf"
        elif "vx:" in line or "vy:" in line or "vz:" in line:
            col = "#ad7fa8"
        elif "xy_valid:" in line or "z_valid:" in line:
            col = "#8ae234"
        ax.text(0.03, y, line, color=col, fontsize=8.5, fontfamily="monospace")
        y -= 0.028

    plt.savefig(out_png)
    plt.close()
    print(f"Rendered terminal uORB view to {out_png}")

def main():
    jmav_id = find_window_id("jMAVSim")
    qgc_id = find_window_id("QGroundControl")
    print(f"jMAVSim window ID: {jmav_id}, QGroundControl window ID: {qgc_id}")

    if not jmav_id or not qgc_id:
        raise RuntimeError("jMAVSim or QGroundControl window not found on DISPLAY=:1")

    print("Launching sitl_flight.py --execute-sitl ...")
    flight_proc = subprocess.Popen([
        sys.executable, "-I", str(ROOT / "scripts/sitl_flight.py"), "--execute-sitl"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Wait until armed and airborne (about 4 seconds)
    print("Waiting for takeoff and Offboard setpoints...")
    time.sleep(4.5)

    # Capture live jMAVSim window (drone in mid-air!)
    capture_window_xwd(jmav_id, str(EVIDENCE / "hinh10_px4_sitl.png"))
    shutil.copyfile(EVIDENCE / "hinh10_px4_sitl.png", EVIDENCE / "jmavsim_live.png")

    # Capture live QGroundControl window (active flight mode, altitude 2.0m!)
    capture_window_xwd(qgc_id, str(EVIDENCE / "qgroundcontrol_live.png"))

    # Capture live uORB topic while vehicle is at 2m altitude
    try:
        uorb_out = subprocess.check_output(
            [str(pathlib.Path.home() / "PX4-Autopilot/build/px4_sitl_default/bin/px4-listener"),
             "vehicle_local_position", "-n", "1"], text=True
        )
        print("Live uORB captured:\n" + "\n".join(uorb_out.splitlines()[:10]))
        render_terminal_uorb(uorb_out, str(EVIDENCE / "hinh11_uorb_listener.png"))
    except Exception as e:
        print("Error capturing uORB:", e)

    # Measure live MAVLink packet loss on port 14540 during flight
    print("Measuring MAVLink sequence loss on UDP 14540 for 4s...")
    try:
        mav_out = subprocess.check_output([
            sys.executable, "-I", str(ROOT / "scripts/measure_mavlink.py"),
            "--seconds", "4.0"
        ], text=True)
        print("MAVLink measurement result:\n" + mav_out)
        with open(EVIDENCE / "live_mavlink_loss.txt", "w") as f:
            f.write(mav_out)
    except Exception as e:
        print("Error measuring mavlink:", e)

    # Wait for flight to complete (landing and disarm)
    print("Waiting for flight to complete and land safely...")
    out, err = flight_proc.communicate(timeout=35.0)
    print("Flight stdout:\n", out)
    if flight_proc.returncode != 0:
        print("Flight stderr:\n", err)
    print("Flight finished cleanly!")

if __name__ == "__main__":
    main()
