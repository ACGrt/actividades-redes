
def check_blocked_hosts(path:str, blocked_hosts:list):
    """
    Given a json list of blocked hosts, checks if the string on the json is in the path.
    """
    for blocked_host in blocked_hosts:
        if blocked_host in path:
            return True
    return False