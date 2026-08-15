def parse_HTTP_message(http_message:bytes):
    """
    Parses an HTTP message and transforms it into a data structure
    for easier access.
    """
    http_message = http_message.decode()
    lines = http_message.splitlines()

    request_line = lines[0]
    method, path, version = request_line.split(' ', 2)
    headers ={}
    for line in lines[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()

    return method, path, version, headers

def clean_http_message(http_message:bytes):
    """
    Cleans an HTTP message by removing everything after \r\n\r\n, 
    which indicates the end of the headers.
    """
    http_message = http_message.decode()
    end_of_headers_index = http_message.find("\r\n\r\n")
    if end_of_headers_index != -1:
        return http_message[:end_of_headers_index + 4].encode()
    
    return http_message.encode()


def receive_full_header(connection_socket, buff_size, end_sequence):
    """
    Retorna los headers y el body que se infiltró
    """
    full_message = b''

    while end_sequence not in full_message:
        recv_message = connection_socket.recv(buff_size)
        if not recv_message:
            break
        full_message += recv_message

    cut = full_message.find(end_sequence) + len(end_sequence)
    headers = full_message[:cut]
    body_infiltrado = full_message[cut:]
    return headers, body_infiltrado

def receive_full_body(connection_socket, buff_size, content_length, body_infiltrado):
    """
    Receives the full body of an HTTP message based on the specified content length.
    And adds the missing part that the receive_full_header function returns.
    """
    full_body = b''
    bytes_received = len(body_infiltrado)
    if content_length == 0:
        return full_body

    full_body += body_infiltrado

    while bytes_received < content_length:
        print(f"Recibiendo body, bytes recibidos: {bytes_received}, content_length: {content_length}")
        recv_message = connection_socket.recv(buff_size)

        if not recv_message:
            break
        full_body += recv_message
        bytes_received += len(recv_message)

    return full_body