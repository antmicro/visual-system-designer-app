# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys
import yaml

from functools import wraps
from pathlib import Path


# Global VSD environment
__vsd_workspace = None
__vsd_env = None


def setup_vsd_env():
    """
    Setup environment for VSD app from initialized VSD workspace.

    Ensures that we know where the VSD_WORKSPACE (default location is cwd) is
    and sets up all env variables needed by commands (with values read from <workspace>/vsd-env.yml).
    """
    global __vsd_workspace
    global __vsd_env

    if __vsd_workspace:
        return

    if "VSD_WORKSPACE" in os.environ:
        workspace = Path(os.environ.get("VSD_WORKSPACE"))
    else:
        workspace = Path(".")

    if not (workspace / "vsd-env.yml").exists():
        logging.error(
            f"Can't find {workspace / 'vsd-env.yml'}. Have you initilized VSD workspace?\n"
            "Run `vsd init [workspace dir]` or export VSD_WORKSPACE dir with intialized workspace."
        )
        sys.exit(1)

    # Set environ variables defined in vsd-env.yml
    with open(workspace / "vsd-env.yml") as f:
        vars = yaml.safe_load(f)

    os.environ.update(vars)

    __vsd_workspace = workspace
    __vsd_env = vars


def setup_env(func):
    """
    Decorator used to setup VSD environment before executing command.
    """
    @wraps(func)
    def inner(*args, **kwargs):
        if not __vsd_env:
            setup_vsd_env()
        return func(*args, **kwargs)
    return inner


def _vsd_env_not_found_err():
    logging.error(
        "VSD environment not found.\n"
        "Consider calling vsd.env.setup_vsd_env() or decorate your current function with vsd.env.setup_env"
    )
    sys.exit(1)


def get_workspace():
    if not __vsd_workspace:
        _vsd_env_not_found_err()
    return __vsd_workspace


def get_var(var_name):
    if not __vsd_workspace:
        _vsd_env_not_found_err()
    return __vsd_env.get(var_name)


def get_env():
    if not __vsd_workspace:
        _vsd_env_not_found_err()
    return __vsd_env.copy()
