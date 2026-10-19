import sys
from SocketTCP import SocketTCP

# Usage: python3 cliente.py <host> <port> [--debug] [--debug-cc] [--gbn] [--no-cc] < archivo.txt
# --gbn uses Go-Back-N, with congestion control unless --no-cc is given
if len(sys.argv) < 3:
    print(f"Usage: python3 {sys.argv[0]} <host> <port> [--debug] [--debug-cc] [--gbn] [--no-cc] < file", file=sys.stderr)
    sys.exit(1)

host, port = sys.argv[1], int(sys.argv[2])
SocketTCP.DEBUG = "--debug" in sys.argv[3:]
SocketTCP.DEBUG_CC = "--debug-cc" in sys.argv[3:]
mode = "go_back_n" if "--gbn" in sys.argv[3:] else "stop_and_wait"

message = sys.stdin.buffer.read()

client_socketTCP = SocketTCP()
client_socketTCP.set_congestion_control_on("--no-cc" not in sys.argv[3:])
client_socketTCP.connect((host, port))
client_socketTCP.send(message, mode)
client_socketTCP.close()

print(f"[{len(message)} bytes sent to {host}:{port}]")
