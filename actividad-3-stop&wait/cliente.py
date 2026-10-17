import sys
from SocketTCP import SocketTCP

# Usage: python3 cliente.py <host> <port> [--debug] < archivo.txt
if len(sys.argv) < 3:
    print(f"Usage: python3 {sys.argv[0]} <host> <port> [--debug] < file", file=sys.stderr)
    sys.exit(1)

host, port = sys.argv[1], int(sys.argv[2])
SocketTCP.DEBUG = "--debug" in sys.argv[3:]

message = sys.stdin.buffer.read()

client_socketTCP = SocketTCP()
client_socketTCP.connect((host, port))
client_socketTCP.send(message)
client_socketTCP.close()

print(f"[{len(message)} bytes sent to {host}:{port}]")
