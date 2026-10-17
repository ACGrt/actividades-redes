import sys
from SocketTCP import SocketTCP

# Usage: python3 server.py [host] [port] [--debug]
args = [arg for arg in sys.argv[1:] if arg != "--debug"]
host = args[0] if len(args) > 0 else "localhost"
port = int(args[1]) if len(args) > 1 else 8000
SocketTCP.DEBUG = "--debug" in sys.argv[1:]

BUFF_SIZE = 64

server_socketTCP = SocketTCP()
server_socketTCP.bind((host, port))
print(f"Server listening on {host}:{port}...", file=sys.stderr)

connection_socketTCP, new_address = server_socketTCP.accept()

message = b""
while True:
    message += connection_socketTCP.recv(BUFF_SIZE)
    if connection_socketTCP.remaining == 0 and not connection_socketTCP.recv_buffer:
        break

connection_socketTCP.recv_close()

print(message.decode("utf-8", errors="replace"), end="", flush=True)
print(f"\n[{len(message)} bytes received]", file=sys.stderr)