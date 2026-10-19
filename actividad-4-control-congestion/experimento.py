import sys
import threading
import time
from SocketTCP import SocketTCP

# Sends a file with Go-Back-N, with and without congestion control, and measures
# how long send takes and how many data segments it sends (retransmissions included).
# Usage: python3 experimento.py <archivo> [repeticiones]      (default: 5 repetitions)
# To test with losses: sudo tc qdisc add dev lo root netem loss 20%

HOST, PORT = "localhost", 8300
TIMEOUT = 0.5

if len(sys.argv) < 2:
    print(f"Usage: python3 {sys.argv[0]} <archivo> [repeticiones]", file=sys.stderr)
    sys.exit(1)

with open(sys.argv[1], "rb") as file:
    message = file.read()
repetitions = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def receive_message(server_socketTCP, result):
    connection_socketTCP, _ = server_socketTCP.accept()
    received = b""
    while True:
        received += connection_socketTCP.recv(64, "go_back_n")
        if connection_socketTCP.remaining == 0 and not connection_socketTCP.recv_buffer:
            break
    result["message"] = received
    connection_socketTCP.recv_close()


def run(port, congestion_control_on):
    server_socketTCP = SocketTCP()
    server_socketTCP.settimeout(TIMEOUT)
    server_socketTCP.bind((HOST, port))
    result = {}
    server_thread = threading.Thread(target=receive_message, args=(server_socketTCP, result))
    server_thread.start()

    client_socketTCP = SocketTCP()
    client_socketTCP.settimeout(TIMEOUT)
    client_socketTCP.set_congestion_control_on(congestion_control_on)
    client_socketTCP.connect((HOST, port))
    start = time.time()
    client_socketTCP.send(message, "go_back_n")
    elapsed = time.time() - start
    client_socketTCP.close()
    server_thread.join()
    server_socketTCP.udp_socket.close()

    return elapsed, client_socketTCP.number_of_sent_segments, result["message"] == message


print(f"{len(message)} bytes, timeout = {TIMEOUT} s, {repetitions} repetitions")
port = PORT
for congestion_control_on in (True, False):
    label = "with congestion control" if congestion_control_on else "without congestion control"
    times, segments = [], []
    for i in range(repetitions):
        elapsed, sent_segments, passed = run(port, congestion_control_on)
        port += 2  # each run uses port and port + 1
        times.append(elapsed)
        segments.append(sent_segments)
        print(f"{label}, run {i + 1}: {elapsed:.2f} s, {sent_segments} segments, "
              f"{'Passed' if passed else 'Failed'}")
    print(f"{label}, average: {sum(times) / repetitions:.2f} s, "
          f"{sum(segments) / repetitions:.1f} segments\n")
