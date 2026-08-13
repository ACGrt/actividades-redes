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

def contains_end_of_message(message:str, end_sequence:str):
    """
    Checks if the given message contains the specified end sequence.
    """
    return end_sequence in message

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
    recv_message= connection_socket.recv(buff_size)
    
    full_message = recv_message

    is_end_of_message = contains_end_of_message(full_message.decode(), end_sequence)

    print("Entrando al while")
    while not is_end_of_message:
        recv_message = connection_socket.recv(buff_size)
        full_message += recv_message
        print(full_message.decode())
        is_end_of_message = contains_end_of_message(full_message.decode(), end_sequence)

    print("Limpieando mensaje")
    full_message = clean_http_message(full_message)
    return full_message

def receive_full_body(connection_socket, buff_size, content_length):
    """
    Receives the full body of an HTTP message based on the specified content length.
    """
    full_body = b''
    bytes_received = 0
    if content_length == 0:
        return full_body


    while bytes_received < content_length:
        print(f"Recibiendo body, bytes recibidos: {bytes_received}, content_length: {content_length}")
        recv_message = connection_socket.recv(buff_size)

        full_body += recv_message
        bytes_received += len(recv_message)

    return full_body