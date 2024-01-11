#!/usr/bin/env python

# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import logging
import typer

from vsd.build import build_zephyr, prepare_zephyr_board
from vsd.backend import start_vsd_app
from vsd.simulate import prepare_renode_files, simulate
from vsd.init import init, vsd_workspace_info
from vsd.env import setup_env

app = typer.Typer(no_args_is_help=True, add_completion=False)

app.command()(init)

app.command()(setup_env(prepare_zephyr_board))

app.command()(setup_env(build_zephyr))

app.command()(setup_env(prepare_renode_files))

app.command()(setup_env(simulate))

app.command("run")(setup_env(start_vsd_app))

app.command("info")(setup_env(vsd_workspace_info))


def main():
    logging.addLevelName(logging.INFO, "\033[1;34m%s\033[1;0m" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))

    app()


if __name__ == "__main__":
    main()
