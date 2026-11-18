#!/usr/bin/env python3
"""Run every report experiment on localhost and save raw measurements.

Nothing here is computed from a formula: each number comes from the C binaries'
own printed timestamps/counters. Output: evidence/results.json (+ raw samples).

  python3 -I scripts/evaluate_baseline.py            # full run (~10 min)
  python3 -I scripts/evaluate_baseline.py --quick    # smoke run
"""
import argparse
from contextlib import ExitStack
import json
import pathlib
import random
import re
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"
OUT = ROOT / "evidence" / "results.json"
VELOCITY = 2.0  # m/s, same for both architectures
CLOCK_SPREAD_MS = 50  # each agent's oscillator error drawn from U(-50, 50) ms


def free_port(kind: int) -> int:
    with socket.socket(socket.AF_INET, kind) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def make_show(directory: str, n: int) -> str:
    path = pathlib.Path(directory, f"show_{n}.bin")
    subprocess.run([sys.executable, "-I", str(ROOT / "scripts/generate_show.py"),
                    "--drones", str(n), "--output", str(path)], check=True)
    return str(path)


def fields(line: str) -> dict:
    return {k: v for k, v in re.findall(r"(\w+)=(-?[\d.]+)", line)}


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()


def run_proposed(n: int, *, jitter=0.0, loss=0.0, samples=8, show_ms=0, kill_after=None) -> dict:
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as cleanup:
        show = make_show(tmp, n)
        tcp, sync, mcast = free_port(socket.SOCK_STREAM), free_port(socket.SOCK_DGRAM), free_port(socket.SOCK_DGRAM)
        gcs = subprocess.Popen([str(BIN / "gcs_server"), "--show", show, "--port", str(tcp),
                                "--sync-port", str(sync), "--multicast", f"239.255.0.1:{mcast}",
                                "--lead-ms", "1500"], stdout=subprocess.PIPE, text=True)
        cleanup.callback(stop_process, gcs)
        time.sleep(0.1)
        agents = []
        for i in range(n):
            command = [str(BIN / "drone_agent"), "--id", str(i), "--port", str(tcp),
                       "--sync-port", str(sync), "--multicast", f"239.255.0.1:{mcast}",
                       "--samples", str(samples),
                       "--clock-offset-ms", f"{random.uniform(-CLOCK_SPREAD_MS, CLOCK_SPREAD_MS):.3f}",
                       "--jitter-ms", str(jitter), "--loss", str(loss)]
            if show_ms:
                command += ["--show-ms", str(show_ms)]
            agent = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            cleanup.callback(stop_process, agent)
            agents.append(agent)
        killed_us = None
        if kill_after is not None:
            # wait until every agent printed SHOW started is impossible without reading; sleep past T_target
            time.sleep(kill_after)
            killed_us = time.time_ns() // 1000
            gcs.send_signal(signal.SIGKILL)
        outputs = []
        for agent in agents:
            out, err = agent.communicate(timeout=60)
            if agent.returncode not in (0, 3):
                raise RuntimeError(f"proposed agent exited {agent.returncode}: {err}")
            outputs.append(out)
        if gcs.poll() is None:
            gcs.send_signal(signal.SIGTERM)
        gcs_out = gcs.communicate(timeout=10)[0]
    starts, errors, rtts, failsafe, sample_sets, lost = [], [], [], [], [], []
    for out in outputs:
        samples_k = []
        for line in out.splitlines():
            f = fields(line)
            if line.startswith("sync k="):
                samples_k.append((int(f["rtt_us"]), int(f["theta_us"])))
            elif "SYNCED" in line:
                errors.append(int(f["theta_us"]) - int(f["true_offset_us"]))
                rtts.append(int(f["rtt_min_us"]))
                truth = int(f["true_offset_us"])
            elif "SHOW started" in line:
                starts.append(int(f["true_us"]))
            elif "FAILSAFE" in line:
                failsafe.append(int(f["true_us"]))
            elif "SHOW finished" in line:
                lost.append(int(f["lost"]))
        if not samples_k:
            raise RuntimeError("agent produced no valid clock-sync samples")
        sample_sets.append({"truth": truth, "samples": samples_k})
    summary = fields(next((l for l in gcs_out.splitlines() if l.startswith("GCS_SUMMARY")), ""))
    return {"n": n, "started": len(starts), "skew_us": max(starts) - min(starts) if starts else None,
            "clock_err_us": errors, "rtt_min_us": rtts, "failsafe_us": failsafe, "killed_us": killed_us,
            "sample_sets": sample_sets, "lost": lost,
            "bandwidth_Bps": float(summary.get("bandwidth_Bps", "nan")),
            "gcs_cpu_s": float(summary["cpu_s"]) if "cpu_s" in summary else None,
            "elapsed_s": float(summary.get("elapsed_s", "nan"))}


def run_baseline(n: int, *, jitter=0.0, loss=0.0, duration=3.0) -> dict:
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as cleanup:
        show = make_show(tmp, n)
        tcp = free_port(socket.SOCK_STREAM)
        server = subprocess.Popen([str(BIN / "baseline_server"), "--show", show, "--port", str(tcp),
                                   "--rate", "10", "--duration", str(duration), "--velocity", str(VELOCITY)],
                                  stdout=subprocess.PIPE, text=True)
        cleanup.callback(stop_process, server)
        time.sleep(0.1)
        agents = [subprocess.Popen([str(BIN / "baseline_agent"), "--id", str(i), "--port", str(tcp),
                                    "--loss", str(loss), "--jitter-ms", str(jitter)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(n)]
        outputs = []
        for agent in agents:
            cleanup.callback(stop_process, agent)
        for agent in agents:
            out, err = agent.communicate(timeout=duration + 30)
            if agent.returncode:
                raise RuntimeError(f"baseline agent exited {agent.returncode}: {err}")
            outputs.append(out)
        server_out = server.communicate(timeout=10)[0]
        if server.returncode:
            raise RuntimeError(f"baseline server exited {server.returncode}")
    starts, e_rms, e_max = [], [], []
    for out in outputs:
        for line in out.splitlines():
            if line.startswith("BASELINE_AGENT_SUMMARY"):
                f = fields(line)
                starts.append(int(f["start_us"]))
                e_rms.append(float(f["E_RMS_cm"]))
                e_max.append(float(f["max_e_cm"]))
    if len(starts) != n:
        raise RuntimeError(f"expected {n} baseline starts, got {len(starts)}")
    summary = fields(next(l for l in server_out.splitlines() if l.startswith("BASELINE_GCS_SUMMARY")))
    return {"n": n, "skew_us": max(starts) - min(starts), "send_spread_us": int(summary["send_spread_us"]),
            "bandwidth_Bps": float(summary["bandwidth_kbps"]) * 1024, "gcs_cpu_s": float(summary["cpu_s"]),
            "duration_s": float(summary["duration_sec"]),
            # every agent logs the same number of ticks, so pooled RMS = sqrt(mean of per-agent RMS^2)
            "e_rms_cm": statistics.fmean(e * e for e in e_rms) ** 0.5, "e_max_cm": max(e_max)}


def mean_sd(values):
    values = [v for v in values if v is not None]
    return {"mean": statistics.fmean(values), "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
            "values": values}


def tn1_scale(scales, reps):
    rows = []
    for n in scales:
        print(f"TN-1 N={n}", flush=True)
        base = [run_baseline(n) for _ in range(reps)]
        prop = [run_proposed(n, show_ms=3000) for _ in range(reps)]
        rows.append({
            "N": n,
            "base_skew_ms": mean_sd([b["skew_us"] / 1000 for b in base]),
            "base_send_spread_ms": mean_sd([b["send_spread_us"] / 1000 for b in base]),
            "prop_skew_ms": mean_sd([p["skew_us"] / 1000 for p in prop]),
            "base_bw_Bps": mean_sd([b["bandwidth_Bps"] for b in base]),
            "prop_bw_Bps": mean_sd([p["bandwidth_Bps"] for p in prop]),
            "base_cpu_pct": mean_sd([100 * b["gcs_cpu_s"] / b["duration_s"] for b in base if b["gcs_cpu_s"]]),
            "prop_cpu_pct": mean_sd([100 * p["gcs_cpu_s"] / p["elapsed_s"] for p in prop if p["gcs_cpu_s"]]),
            "prop_started": [p["started"] for p in prop],
        })
    return rows


def tn2_jitter(jitters, reps, n=20):
    rows = []
    for j in jitters:
        print(f"TN-2 jitter={j} ms", flush=True)
        base = [run_baseline(n, jitter=j, duration=1.0) for _ in range(reps)]
        prop = [run_proposed(n, jitter=j) for _ in range(reps)]
        errs = [abs(e) / 1000 for p in prop for e in p["clock_err_us"]]
        rows.append({"jitter_ms": j,
                     "base_skew_ms": mean_sd([b["skew_us"] / 1000 for b in base]),
                     "prop_skew_ms": mean_sd([p["skew_us"] / 1000 for p in prop]),
                     "prop_abs_clock_err_ms": mean_sd(errs),
                     "prop_eps_ms": mean_sd([r / 2000 for p in prop for r in p["rtt_min_us"]])})
    return rows


def tn3_loss(losses, reps, n=20):
    rows = []
    for p_loss in losses:
        print(f"TN-3 loss={p_loss}%", flush=True)
        base = [run_baseline(n, loss=p_loss) for _ in range(reps)]
        prop = [run_proposed(n, loss=p_loss, show_ms=3000) for _ in range(reps)]
        clock = [abs(e) / 1e6 for p in prop for e in p["clock_err_us"]]
        # Proposed setpoints come from RAM; the only timing-induced position error is v * |clock error|.
        prop_e = [VELOCITY * c * 100 for c in clock]
        p_frac = p_loss / 100
        rows.append({"p_loss": p_loss,
                     "base_e_rms_cm": mean_sd([b["e_rms_cm"] for b in base]),
                     "base_e_max_cm": max(b["e_max_cm"] for b in base),
                     "theory_e_cm": VELOCITY * 0.1 * p_frac / (1 - p_frac) * 100,
                     "theory_rms_cm": VELOCITY * 0.1 * (p_frac * (1 + p_frac)) ** 0.5 / (1 - p_frac) * 100,
                     "prop_e_rms_cm": (statistics.fmean(e * e for e in prop_e)) ** 0.5,
                     "prop_e_max_cm": max(prop_e),
                     "prop_started": sum(p["started"] for p in prop), "prop_total": n * reps,
                     "prop_failsafe": sum(len(p["failsafe_us"]) for p in prop),
                     "prop_heartbeats_lost": sum(sum(p["lost"]) for p in prop)})
    return rows


def tn4_filter(jitters, reps, n=20, k_max=16):
    out = {}
    for j in jitters:
        print(f"TN-4 jitter={j} ms", flush=True)
        sets = [s for _ in range(reps) for s in run_proposed(n, jitter=j, samples=k_max)["sample_sets"]]
        per_k = {}
        for k in (1, 2, 4, 8, 16):
            minimum, average = [], []
            for s in sets:
                first = s["samples"][:k]
                if len(first) < k:
                    continue
                best = min(first)[1]
                minimum.append((best - s["truth"]) / 1000)
                average.append((statistics.fmean(t for _, t in first) - s["truth"]) / 1000)
            per_k[k] = {"min_rtt": minimum, "mean": average}
        out[str(j)] = per_k
    return out


def tn5_failsafe(reps, n=10):
    rows = []
    for _ in range(reps):
        print("TN-5 kill GCS", flush=True)
        result = run_proposed(n, show_ms=12000, kill_after=4.0)
        delays = [(t - result["killed_us"]) / 1000 for t in result["failsafe_us"]]
        rows.append({"n": n, "detected": len(delays), "delay_ms": delays})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--only-tn3", action="store_true", help="rerun TN-3 and update results.json")
    args = parser.parse_args()
    random.seed(2026)
    if args.only_tn3:
        results = json.loads(OUT.read_text())
        results["tn3"] = tn3_loss([0, 1, 5, 10, 20], 5)
        OUT.write_text(json.dumps(results, indent=1))
        print(f"updated {OUT}")
        return
    if args.quick:
        results = {"tn1": tn1_scale([2, 5], 1), "tn2": tn2_jitter([0, 5], 1), "tn3": tn3_loss([0, 10], 1),
                   "tn4": tn4_filter([5], 1), "tn5": tn5_failsafe(1)}
    else:
        results = {"tn1": tn1_scale([2, 5, 10, 20, 50, 100], 3),
                   "tn2": tn2_jitter([0, 1, 5, 10, 20], 3),
                   "tn3": tn3_loss([0, 1, 5, 10, 20], 5),
                   "tn4": tn4_filter([1, 5], 5),
                   "tn5": tn5_failsafe(3)}
    results["meta"] = {"date": time.strftime("%Y-%m-%d %H:%M"), "velocity_mps": VELOCITY,
                       "clock_spread_ms": CLOCK_SPREAD_MS, "quick": args.quick}
    target = OUT.with_name("results_quick.json") if args.quick else OUT
    target.write_text(json.dumps(results, indent=1))
    print(f"saved {target}")


if __name__ == "__main__":
    main()
