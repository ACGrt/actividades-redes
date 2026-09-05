def create_HTTP_message(method, path, version, headers):
    r"""
    Builds the head of an HTTP message: first line, headers, and the empty
    line that closes them.

    Used for both directions. When forwarding a request the three fields are
    (method, path, version); when forwarding a response they are the fields of
    the status line, in the same order parse_HTTP_message returns them.

    Returns the head encoded as bytes, ending in \r\n\r\n. The body, if any,
    must be appended by the caller.
    """
    request_line = f"{method} {path} {version}\r\n"
    headers_lines = ''.join(f"{key}: {value}\r\n" for key, value in headers.items())
    return (request_line + headers_lines + "\r\n").encode()
