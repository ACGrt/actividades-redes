def parse_HTTP_message(http_message:bytes):
    """
    Splits the head of an HTTP message into its components.

    Works for both requests and responses, since the request line
    ("GET /path HTTP/1.1") and the status line ("HTTP/1.1 404 Not Found")
    both have three space-separated fields. Lines without a colon are ignored.

    Returns a (method, path, version, headers) tuple, where the first three
    are the fields of the first line and headers is a name -> value dict.
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

def receive_full_header(connection_socket, buff_size, end_sequence):
    r"""
    Reads the head of an HTTP message from a socket, no matter how small
    the buffer is.

    Every read is appended to an accumulator and the end sequence (\r\n\r\n)
    is searched for in that accumulator, not in the last read, so the
    delimiter is still found when it is split across two reads.

    Reading in fixed-size blocks means the last read usually overshoots the
    delimiter and pulls in the first bytes of the body. Those bytes cannot be
    put back into the socket, so they are returned separately and must be
    handed over to receive_full_body.

    Returns a (headers, body_infiltrado) tuple of bytes. Stops early if the
    peer closes the connection, in which case headers may be incomplete.
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
    Reads the body of an HTTP message from a socket until content_length
    bytes have been collected.

    The body has no delimiter (any byte sequence is valid inside it), so the
    only way to know it is complete is to count. The count starts at the
    length of body_infiltrado, the leftover bytes receive_full_header already
    took out of the socket; starting at zero would read content_length extra
    bytes and block forever waiting for data that never arrives.

    Returns the full body as bytes, prepending body_infiltrado. Returns empty
    bytes when content_length is 0, since reading would also block there.
    Stops early if the peer closes the connection.
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