import socket
from SocketTCP import SocketTCP

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 8000))

while True:
    raw, _ = sock.recvfrom(SocketTCP.BUFFER_SIZE)
    segment = SocketTCP.parse_segment(raw)
    if segment["fin"]:
        break
    print(segment["data"].decode("utf-8", errors="replace"), end="", flush=True)