import sys
import threading
from SocketTCP import SocketTCP

# Sends a message of 2n bytes and reads it with two calls to recv(n).
# Usage: python3 test2n.py [n ...] [--debug]      (default n: 7 25 37, not multiples of 16)
# To test with losses: sudo tc qdisc add dev lo root netem loss 20%

HOST, PORT = "localhost", 8100

args = [arg for arg in sys.argv[1:] if arg != "--debug"]
n_values = [int(arg) for arg in args] or [7, 25, 37]
SocketTCP.DEBUG = "--debug" in sys.argv[1:]


def receive_in_two_parts(server_socketTCP, n, result):
    connection_socketTCP, _ = server_socketTCP.accept()
    result["part_1"] = connection_socketTCP.recv(n)
    result["part_2"] = connection_socketTCP.recv(n)
    connection_socketTCP.recv_close()


for i, n in enumerate(n_values):
    port = PORT + 2 * i  # each test uses port and port + 1
    message = bytes(ord("A") + j % 26 for j in range(2 * n))

    server_socketTCP = SocketTCP()
    server_socketTCP.bind((HOST, port))
    result = {}
    server_thread = threading.Thread(target=receive_in_two_parts, args=(server_socketTCP, n, result))
    server_thread.start()

    client_socketTCP = SocketTCP()
    client_socketTCP.connect((HOST, port))
    client_socketTCP.send(message)
    client_socketTCP.close()
    server_thread.join()
    server_socketTCP.udp_socket.close()

    passed = result["part_1"] == message[:n] and result["part_2"] == message[n:]
    print(f"n={n} ({2 * n} bytes): recv(n) -> {len(result['part_1'])} + {len(result['part_2'])} bytes, "
          f"{'Passed' if passed else 'Failed'}")
