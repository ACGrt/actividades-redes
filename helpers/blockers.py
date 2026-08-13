
def check_blocked_hosts(path:str, blocked_hosts:list):
    """
    Given a json list of blocked hosts, checks if the string on the json is in the path.
    """
    for blocked_host in blocked_hosts:
        if blocked_host in path:
            return True
    return False

def replace_forbidden_words(response:str, forbidden_words:list):
    """
    Given a json list of forbidden words, checks the server HTML response for the
    presence of any of the forbidden words. If any of the forbidden words is found, it replaces it
    with the corresponding replacement string from the json.
    """
    for forbidden_word in forbidden_words:
        for word, replacement in forbidden_word.items():
            if word in response:
                response = response.replace(word, replacement)
    return response