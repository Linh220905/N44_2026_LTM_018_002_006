#!/usr/bin/env python3
"""Create high quality composite for Hinh 10: jMAVSim 3D simulation + QGroundControl."""
from PIL import Image, ImageDraw, ImageFont
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"

img_jmav = Image.open(EVIDENCE / "jmavsim_live.png")
img_qgc = Image.open(EVIDENCE / "qgroundcontrol_live.png")

# Target height: 731
# Scale QGC to match height or side by side
# Target: Side-by-side composite
target_h = 700
w_jmav = int(img_jmav.width * (target_h / img_jmav.height))
w_qgc = int(img_qgc.width * (target_h / img_qgc.height))

jmav_resized = img_jmav.resize((w_jmav, target_h), Image.Resampling.LANCZOS)
qgc_resized = img_qgc.resize((w_qgc, target_h), Image.Resampling.LANCZOS)

header_h = 45
total_w = w_jmav + w_qgc + 20
total_h = target_h + header_h

comp = Image.new("RGBA", (total_w, total_h), (245, 247, 250, 255))
draw = ImageDraw.Draw(comp)

# Paste images
comp.paste(jmav_resized, (0, header_h))
comp.paste(qgc_resized, (w_jmav + 20, header_h))

# Draw labels
draw.rectangle([(0, 0), (w_jmav, header_h)], fill=(33, 43, 54, 255))
draw.text((15, 12), "PX4 SITL · jMAVSim 3D Vehicle Simulation", fill=(255, 255, 255, 255))

draw.rectangle([(w_jmav + 20, 0), (total_w, header_h)], fill=(16, 37, 66, 255))
draw.text((w_jmav + 35, 12), "QGroundControl 4.4.5 · Live Telemetry & Mission Control", fill=(255, 255, 255, 255))

comp.save(EVIDENCE / "hinh10_px4_sitl.png")
print("Saved composite Hinh 10:", comp.size)
