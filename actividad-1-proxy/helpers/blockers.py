
def check_blocked_hosts(path:str, blocked_hosts:list):
    """
    Tells whether a request must be blocked.

    Matching is done by substring against the requested path, so an entry in
    the config can be a host ("example.com"), a path ("/secret") or any
    fragment of the URI.

    Returns True if any entry of blocked_hosts appears in path.
    """
    for blocked_host in blocked_hosts:
        if blocked_host in path:
            return True
    return False

def replace_forbidden_words(response:str, forbidden_words:list):
    """
    Censors the body of a server response.

    forbidden_words is the list of single-entry {word: replacement} dicts read
    from the config file. Every occurrence of each word is replaced.

    Returns the censored text. Note that the result can differ in length from
    the input, so the caller must recompute Content-Length before forwarding
    the response.
    """
    for forbidden_word in forbidden_words:
        for word, replacement in forbidden_word.items():
            if word in response:
                response = response.replace(word, replacement)
    return response