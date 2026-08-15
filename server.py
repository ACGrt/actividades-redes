import base64
import socket
import sys
import json
from helpers.blockers import check_blocked_hosts, replace_forbidden_words
from helpers.createMSG import create_HTTP_message
from helpers.parsers import parse_HTTP_message, receive_full_body, receive_full_header



if len(sys.argv) < 2:
    print("Error: falta el archivo JSON")
    sys.exit(1)
ruta_json = sys.argv[1]
with open(ruta_json, 'r') as archivo:
    configuration = json.load(archivo)

HOST = '0.0.0.0'
PORT = 8080
BLOCKED_IMAGE_PATH = "/__proxy__/blocked.jpg"
with open("cat.jpg", "rb") as image_file:
    imagen_bytes = image_file.read()


buff_size = 10
end_of_message = b'\r\n\r\n'

proxy_socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
proxy_socket.bind((HOST,PORT))
proxy_socket.listen()

print(f"Server escuchando en puerto:{PORT}...")


while True:
    client_connection, client_address = proxy_socket.accept()
    print(f" Conexion entrante desde {client_address}")

    recv_message, body_infiltrado = receive_full_header(client_connection, buff_size, end_of_message)

    client_method, client_path, client_version, client_headers = parse_HTTP_message(recv_message)
    host_destino = client_headers["Host"]

    print(f"Host destino: {host_destino}")
    print(f"Path destino: {client_path}")

    if client_path.endswith(BLOCKED_IMAGE_PATH):
        header = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(imagen_bytes)}\r\n"
            "Connection: close\r\n\r\n"
        )
        server_bytes = header.encode() + imagen_bytes

        client_connection.sendall(server_bytes)
        client_connection.close()
        continue

    if check_blocked_hosts(client_path, configuration["blocked"]):
        print(f"Path bloqueado: {client_path}")
        body = f'<html><body><img src = "{BLOCKED_IMAGE_PATH}"></body></html>'.encode()

        header = (
            "HTTP/1.1 403 Forbidden\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        )
        server_bytes = header.encode() + body
        client_connection.sendall(server_bytes)
        client_connection.close()
        continue

    print(f"Estableciendo conexión con {host_destino}...")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.connect((host_destino, 80))

    client_headers["X-ElQuePregunta"] = configuration["user"]
    modified_client_bytes = create_HTTP_message(client_method, client_path, client_version, client_headers)

    server_socket.send(modified_client_bytes)

    server_headers, body_infiltrado = receive_full_header(server_socket, buff_size, end_of_message)

    print("Headers del servidor:")
    print(server_headers.decode())

    server_method, server_path, server_version, server_headers_dict = parse_HTTP_message(server_headers)
    content_length = int(server_headers_dict.get("Content-Length", 0))
    print(content_length)
    server_body = receive_full_body(server_socket, buff_size, content_length, body_infiltrado)

    server_bytes = server_headers + server_body
    
    purified_body = replace_forbidden_words(
        server_body.decode(), configuration["forbidden_words"]
        ).encode()

    if "Content-Length" in server_headers_dict:
        server_headers_dict["Content-Length"] = str(len(purified_body))

    response_bytes = create_HTTP_message(
        server_method, server_path, server_version, server_headers_dict
    ) + purified_body

    client_connection.send(response_bytes)
    client_connection.close()
