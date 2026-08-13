def create_HTTP_message(method, path, version, headers):
    """
    Creates an HTTP message from the given method, path, version, and headers.
    """
    request_line = f"{method} {path} {version}\r\n"
    headers_lines = ''.join(f"{key}: {value}\r\n" for key, value in headers.items())
    return (request_line + headers_lines + "\r\n").encode()
