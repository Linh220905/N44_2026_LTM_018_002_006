"""End-to-end localhost smoke test; run with python3 -I tests/test_swarm.py."""
import pathlib
import sys
import struct
import socket
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    show = pathlib.Path(directory, "show.bin")
    subprocess.run([sys.executable, "-I", str(ROOT / "scripts/generate_show.py"),
                    "--drones", "2", "--shape", "heart", "--output", str(show)], check=True)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        tcp_port = probe.getsockname()[1]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        udp_port = probe.getsockname()[1]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        sync_port = probe.getsockname()[1]
    # Invalid show must fail before binding network sockets.
    invalid = pathlib.Path(directory, "invalid.bin")
    invalid.write_bytes(b"SHOW\x00\x02")
    assert subprocess.run([str(ROOT / "bin/gcs_server"), "--show", str(invalid),
                           "--port", str(tcp_port)], capture_output=True).returncode != 0
    server = subprocess.Popen([str(ROOT / "bin/gcs_server"), "--show", str(show),
                               "--port", str(tcp_port), "--sync-port", str(sync_port), "--multicast", f"239.255.0.1:{udp_port}"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(0.1)
        # Send HELLO one byte at a time to exercise TCP stream reassembly.
        with socket.create_connection(("127.0.0.1", tcp_port), timeout=3) as client:
            data = struct.pack(">HBBIIHHH", 0x5058, 1, 1, 1, 2, 0, 0, 0)
            crc = 0xffff
            for byte in data:
                crc ^= byte << 8
                for _ in range(8):
                    crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
            frame = data[:12] + struct.pack(">H", crc) + data[14:]
            for byte in frame:
                client.sendall(bytes((byte,)))
            client.settimeout(3)
            assert client.recv(18)[:4] == b"PX\x01\x02"  # HELLO_ACK
        agents = [subprocess.Popen([str(ROOT / "bin/drone_agent"), "--id", str(i),
                                   "--port", str(tcp_port), "--sync-port", str(sync_port), "--multicast", f"239.255.0.1:{udp_port}"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                  for i in range(2)]
        for i, agent in enumerate(agents):
            stdout, stderr = agent.communicate(timeout=12)
            assert agent.returncode == 0, f"agent {i}: {stderr}"
            assert f"drone={i} " in stdout and "SHOW started" in stdout, stdout
            assert "SYNCED theta_us=" in stdout, stdout  # Cristian sync ran before start
        assert server.poll() is None, "GCS exited unexpectedly"
        print("swarm integration passed")
    finally:
        for agent in locals().get("agents", []):
            if agent.poll() is None:
                agent.kill()
                agent.communicate()
        server.terminate()
        try:
            server.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate()
