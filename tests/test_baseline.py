"""Integration test for baseline unicast streaming architecture."""
import pathlib
import sys
import socket
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_baseline_integration():
    with tempfile.TemporaryDirectory() as temp_dir:
        show_file = pathlib.Path(temp_dir, "show.bin")
        # Generate 3-drone show
        subprocess.run([
            sys.executable, "-I", str(ROOT / "scripts/generate_show.py"),
            "--drones", "3", "--shape", "heart", "--output", str(show_file)
        ], check=True)

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            tcp_port = s.getsockname()[1]

        # Launch baseline GCS server
        server = subprocess.Popen([
            str(ROOT / "bin/baseline_server"),
            "--show", str(show_file),
            "--port", str(tcp_port),
            "--rate", "10",
            "--duration", "1.5"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        time.sleep(0.1)

        # Launch 3 baseline agents
        agents = []
        for i in range(3):
            p = subprocess.Popen([
                str(ROOT / "bin/baseline_agent"),
                "--id", str(i),
                "--port", str(tcp_port),
                "--loss", "10.0"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            agents.append(p)

        # Collect agent outputs
        agent_outputs = []
        for i, p in enumerate(agents):
            out, err = p.communicate(timeout=8)
            assert p.returncode == 0, f"agent {i} failed: {err}"
            assert f"BASELINE_AGENT_SUMMARY: id={i}" in out
            agent_outputs.append(out)

        server_out, server_err = server.communicate(timeout=5)
        assert server.returncode == 0, f"server failed: {server_err}"
        assert "BASELINE_GCS_SUMMARY" in server_out

        print("Baseline integration test passed successfully!")

if __name__ == "__main__":
    test_baseline_integration()
