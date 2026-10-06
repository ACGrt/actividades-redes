import socket
from SocketTCP import SocketTCP

IP, PUERTO = "127.0.0.1", 8000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
file_path = input("Ingrese la ruta del archivo a enviar: ")

seq = 0
with open(file_path, "rb") as f:
    while chunk := f.read(SocketTCP.MAX_PAYLOAD):
        segment = SocketTCP.create_segment({"seq": seq, "data": chunk})
        sock.sendto(segment, (IP, PUERTO))
        seq += 1

sock.sendto(SocketTCP.create_segment({"seq": seq, "fin": True}), (IP, PUERTO))
sock.close()