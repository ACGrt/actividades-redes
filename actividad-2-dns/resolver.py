import socket
import sys

from DNS.message import DNSMessage, build_query
from DNS.parser import DNSParser
from DNS.cache import DNSCache

sock_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_client.bind(("10.0.2.15", 8000))
sock_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

root_ip = "198.41.0.4"

consultas_hechas = set()
cache = DNSCache()

DEBUG = "--debug" in sys.argv


def debug(mensaje):
    if DEBUG:
        print(f"(debug) {mensaje}")


def consultando(dominio, ns_name, ip_addr):
    debug(f"Consultando '{dominio}' a '{ns_name}' con direccion IP '{ip_addr}'")


def dominio_de(mensaje_consulta):
    consulta = DNSParser(mensaje_consulta)
    consulta.parseHeader()
    return consulta.parseQuestionSection()["qname"]


def resolver(mensaje_consulta: bytes, ip_addr=root_ip) -> bytes:
    consultas_hechas.add((ip_addr, mensaje_consulta))

    dominio = dominio_de(mensaje_consulta)

    if ip_addr == root_ip:
        consultando(dominio, ".", ip_addr)

    sock_server.sendto(mensaje_consulta, (ip_addr, 53))
    data, _ = sock_server.recvfrom(4096)
    mensaje = DNSMessage(**DNSParser(data).parse())

    if mensaje.has_type_A():
        debug(f"  {ip_addr} responde: {mensaje.get_answer()}")
        return data

    ns_name = mensaje.get_ns_name()
    if ns_name is None:
        debug(f"  {ip_addr} no responde ni deriva")
        return data

    ns_elegido, siguiente_ip = mensaje.get_additional_ns()
    if siguiente_ip is None:
        debug(f"  {ip_addr} deriva a '{ns_name}' sin darnos su IP")
        ns_elegido = ns_name
        respuesta_ns = resolver(build_query(ns_name))
        siguiente_ip = DNSMessage(**DNSParser(respuesta_ns).parse()).get_answer()
        if siguiente_ip is None:
            return data

    consultando(dominio, ns_elegido, siguiente_ip)
    return resolver(mensaje_consulta, siguiente_ip)


while True:
    query_data, client_address = sock_client.recvfrom(4096)
    # El mensaje tal como se recibio, sin decode()
    print(f"Consulta de {client_address}: {query_data}")
    consultas_hechas.clear()

    dominio = dominio_de(query_data)
    guardada = cache.get_dominio(dominio)
    if guardada is not None:
        response_data = query_data[:2] + guardada[2:]
        cache.add(dominio)
        debug(f"'{dominio}' servido desde el cache, sin salir a la red")
    else:
        response_data = resolver(query_data)
        cache.add(dominio, response_data)

    sock_client.sendto(response_data, client_address)
    print(f"Respuesta enviada a {client_address}\n")
