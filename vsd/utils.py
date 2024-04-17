import re


def find_chosen(name, dts_path):
    with open(dts_path, 'r') as f:
        dts = f.read()

    console_m = re.search(f'{name} = &(.+);', dts)
    if not console_m:
        return None

    return console_m.group(1)
