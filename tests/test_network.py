"""Regression checks on real localhost sockets; no PX4 or external packages needed."""
import binascii
from contextlib import contextmanager
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"


def frame(kind, seq, payload=b""):
    data = struct.pack(">HBBIIHH", 0x5058, 1, kind, seq, len(payload), 0, 0) + payload
    return data[:12] + struct.pack(">H", binascii.crc_hqx(data, 0xFFFF)) + data[14:]


def port(kind=socket.SOCK_STREAM):
    with socket.socket(socket.AF_INET, kind) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise AssertionError("truncated TCP frame")
        data += chunk
    return data


@contextmanager
def server(program="gcs_server", lead=1500):
    with tempfile.TemporaryDirectory() as directory:
        show = Path(directory) / "show.bin"
        subprocess.run([sys.executable, "-I", str(ROOT / "scripts/generate_show.py"),
                        "--drones", "1", "--output", str(show)], check=True)
        tcp, sync, udp = port(), port(socket.SOCK_DGRAM), port(socket.SOCK_DGRAM)
        args = [str(BIN / program), "--show", str(show), "--port", str(tcp)]
        if program == "gcs_server":
            args += ["--sync-port", str(sync), "--multicast", f"239.255.0.1:{udp}", "--lead-ms", str(lead)]
        else:
            args += ["--duration", "0.2"]
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            end = time.monotonic() + 3
            while True:
                try:
                    probe = socket.create_connection(("127.0.0.1", tcp), timeout=0.1)
                    probe.close()
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() > end:
                        raise AssertionError("server did not become ready")
                    time.sleep(0.02)
            yield process, tcp, sync, udp
        finally:
            process.terminate()
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


class NetworkTests(unittest.TestCase):
    def test_invalid_arguments(self):
        for name in ("gcs_server", "drone_agent", "baseline_server", "baseline_agent"):
            for value in ("", "abc", "0", "65536", "999999999999999999999"):
                with self.subTest(program=name, port=value):
                    p = subprocess.run([str(BIN / name), "--port", value], capture_output=True, timeout=2)
                    self.assertEqual(p.returncode, 2)
        for name in ("drone_agent", "baseline_agent"):
            for option, value in (("--loss", "nan"), ("--loss", "101"), ("--loss", "-1"),
                                  ("--jitter-ms", "inf"), ("--jitter-ms", "-1")):
                with self.subTest(program=name, option=option, value=value):
                    p = subprocess.run([str(BIN / name), "--id", "0", option, value],
                                       capture_output=True, timeout=2)
                    self.assertEqual(p.returncode, 2)

    def test_fragmented_baseline_hello(self):
        with server("baseline_server") as (process, tcp, _, _):
            with socket.create_connection(("127.0.0.1", tcp), timeout=2) as client:
                data = frame(1, 1, b"\0\0")
                for byte in data:
                    client.sendall(bytes((byte,)))
                    time.sleep(0.002)
                ack = exact(client, 18)
                self.assertEqual(ack[3], 2)
                kinds = []
                while 8 not in kinds:
                    header = exact(client, 16)
                    kinds.append(header[3])
                    exact(client, struct.unpack_from(">I", header, 8)[0])
                self.assertIn(9, kinds)
            self.assertEqual(process.wait(timeout=3), 0)

    def test_emergency_during_start_wait(self):
        with server(lead=3000) as (_, tcp, sync, udp):
            agent = subprocess.Popen([str(BIN / "drone_agent"), "--id", "0", "--port", str(tcp),
                                      "--sync-port", str(sync), "--multicast", f"239.255.0.1:{udp}"],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                # Observe a real trigger to know the agent has entered its pending-start state.
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
                    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    receiver.bind(("", udp))
                    receiver.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                        socket.inet_aton("239.255.0.1") + socket.inet_aton("127.0.0.1"))
                    receiver.settimeout(3)
                    while receiver.recv(64)[3] != 7:
                        pass
                time.sleep(0.1)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                      socket.inet_aton("127.0.0.1"))
                    sender.sendto(frame(8, 100000), ("239.255.0.1", udp))
                output, error = agent.communicate(timeout=1)
                self.assertEqual(agent.returncode, 2, error)
                self.assertNotIn("SHOW started", output)
            finally:
                if agent.poll() is None:
                    agent.kill()
                agent.communicate()

    def test_udp_oversize_is_rejected(self):
        with server() as (_, _, sync, _):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(0.25)
                request = frame(4, 1, struct.pack(">Q", time.time_ns() // 1000))
                client.sendto(request + b"extra", ("127.0.0.1", sync))
                with self.assertRaises(socket.timeout):
                    client.recv(100)
                client.sendto(request, ("127.0.0.1", sync))
                self.assertEqual(client.recv(100)[3], 5)


if __name__ == "__main__":
    unittest.main()
