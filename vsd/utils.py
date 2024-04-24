import re


def find_chosen(name, dts_path):
    with open(dts_path, 'r') as f:
        dts = f.read()

    console_m = re.search(f'{name} = &(.+);', dts)
    if not console_m:
        return None

    return console_m.group(1)


def filter_nodes(connections, filter_fn):
    """
    Use filter_fn to filter nodes on connections list.

    The filter function has signature:
        def filter_fn(if_name, if_type, node) -> bool

    Returns tuple:
        - filtered nodes
        - connections that are not accepted by the filter function
    """
    filtered, other = [], []
    for conn in connections:
        if filter_fn(*conn):
            filtered.append(conn)
        else:
            other.append(conn)
    return filtered, other
