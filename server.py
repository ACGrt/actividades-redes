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

with open("cat.jpg", "rb") as image_file:
    imagen_codificada = base64.b64encode(image_file.read()).decode('utf-8')

HOST = '0.0.0.0'
PORT = 8080

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

    if check_blocked_hosts(client_path, configuration["blocked"]):
        print(f"Path bloqueado: {client_path}")

        header = "HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\n\r\n"
        body = f"""
            <html>
            <body>
                <img src="data:image/jpeg;base64,{imagen_codificada}">
            </body>
            </html>
            """

        server_bytes = (header + body).encode()
        client_connection.send(server_bytes)
        client_connection.close()
        continue

    print(f"Estableciendo conexión con {host_destino}...")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.connect((host_destino, 80))

    client_headers["X-ElQuePregunta"] = configuration["user"]
    modified_client_bytes = create_HTTP_message(client_method, client_path, client_version, client_headers)

    server_socket.send(modified_client_bytes)

    #Esto es un POST, así que para recibir el body debemos fijarnos en el Content-Length
    server_headers, body_infiltrado = receive_full_header(server_socket, buff_size, end_of_message) # se obtiene el header

    print("Headers del servidor:")
    print(server_headers.decode())

    # falta obtener el body del POST, si es que lo hay. Para eso se debe leer el Content-Length del header y leer esa cantidad de bytes del socket.
    server_method, server_path, server_version, server_headers_dict = parse_HTTP_message(server_headers)
    content_length = int(server_headers_dict.get("Content-Length", 0))
    print(content_length)
    server_body = receive_full_body(server_socket, buff_size, content_length, body_infiltrado)

    # Armamos la respuesta completa del servidor, que incluye el header y el body
    server_bytes = server_headers + server_body
    
    purified_response = replace_forbidden_words(server_bytes.decode(), configuration["forbidden_words"])

    client_connection.send(purified_response.encode())
    client_connection.close()
