import logging
import re
import subprocess
import sys

from pathlib import Path
from subprocess import CalledProcessError


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


def git_command(command, repo=Path("."), output=False, error_msg=None):
    try:
        if output:
            return subprocess.check_output(["git", *command], cwd=repo, text=True).strip()
        else:
            subprocess.check_call(["git", *command], cwd=repo)
    except CalledProcessError as e:
        if not error_msg:
            raise
        logging.error(f"{error_msg} (exitcode: {e.returncode})")
        sys.exit(e.returncode)


def git_commit_sha(repo):
    output = git_command(
        command=["rev-parse", "HEAD"],
        repo=repo,
        output=True,
        error_msg=f"Failed to read {repo} commit sha",
    )
    return output.strip()
