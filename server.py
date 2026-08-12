import socket
import sys
import json


def parse_HTTP_message(http_message:bytes):
    """
    Parses an HTTP message and transforms it into a data structure
    for easier access.
    """
    http_message = http_message.decode()
    lines = http_message.splitlines()

    request_line = lines[0]
    method, path, version = request_line.split(' ')

    headers ={}
    for line in lines[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()

    return method, path, version, headers


def create_HTTP_message(method, path, version, headers):
    """
    Creates an HTTP message from the given method, path, version, and headers.
    """
    request_line = f"{method} {path} {version}\r\n"
    headers_lines = ''.join(f"{key}: {value}\r\n" for key, value in headers.items())
    return (request_line + headers_lines + "\r\n").encode()

if len(sys.argv) < 2:
	print("Error: falta el archivo JSON")
	sys.exit(1)
ruta_json = sys.argv[1]
with open(ruta_json, 'r') as archivo:
	configuration = json.load(archivo)
	nombre_usuario = configuration["nombre"]
HOST = '0.0.0.0'
PORT = 8080

server_socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_socket.bind((HOST,PORT))
server_socket.listen()

print(f"Server escuchando en puerto:{PORT}...")


while True:
	client_connection, client_address = server_socket.accept()
	print(f" Conexion entrante desde {client_address}")

	request_bytes = client_connection.recv(1024)


	client_method, client_path, client_version, client_headers = parse_HTTP_message(request_bytes)
	html_body ="<html><body><h1>Hola desde mi servidor en Kali!</h1></body></html>\r\n"
	html_bytes = html_body.encode()

	response_headers = {
		"Content-Type": "text/html",
		"Content-length": str(len(html_bytes)),
		"Connection": "close",
		"X-ElQuePregunta": nombre_usuario
	}
	response_head_bytes = create_HTTP_message("HTTP/1.1", "200", "OK", response_headers)
	
	final_response = response_head_bytes + html_bytes
	client_connection.send(final_response)
	client_connection.close()
