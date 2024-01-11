import logging
import os
import yaml

from functools import wraps
from pathlib import Path


def setup_vsd_env():
    """
    Setup environment for VSD app from initialized VSD workspace.

    Ensures that we know where the VSD_WORKSPACE (default location is cwd) is
    and sets up all env variables needed by commands (with values read from <workspace>/vsd-env.yml).
    """
    if "VSD_WORKSPACE" in os.environ:
        workspace = Path(os.environ.get("VSD_WORKSPACE"))
    else:
        workspace = Path(".")
        os.environ["VSD_WORKSPACE"] = str(workspace.resolve())

    if not (workspace / "vsd-env.yml").exists():
        logging.error(
            f"Can't find {workspace / 'vsd-env.yml'}. Have you initilized VSD workspace?\n"
            "Run `vsd init [workspace dir]` or export VSD_WORKSPACE dir with intialized workspace."
        )
        exit(1)

    # Set environ variables defined in vsd-env.yml
    with open(workspace / "vsd-env.yml") as f:
        vars = yaml.safe_load(f)
    os.environ.update(vars)


def setup_env(func):
    """
    Decorator used to setup VSD environment before executing command.
    """
    @wraps(func)
    def inner(*args, **kwargs):
        setup_vsd_env()
        return func(*args, **kwargs)
    return inner
