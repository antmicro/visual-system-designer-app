#!/usr/bin/env python

# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import typer

from typing import Optional

from vsd.build import build_zephyr, prepare_zephyr_board
from vsd.backend import start_vsd_app
from vsd.simulate import prepare_renode_files, simulate
from vsd.init import init, vsd_workspace_info

app = typer.Typer(no_args_is_help=True, add_completion=False)

app.command()(init)

app.command()(prepare_zephyr_board)

app.command()(build_zephyr)

app.command()(prepare_renode_files)

app.command()(simulate)

app.command("run")(start_vsd_app)

app.command("info")(vsd_workspace_info)


@app.callback()
def set_logging(log_level: Optional[str] = None):
    if not log_level:
        log_level = os.environ.get('LOGLEVEL', 'INFO').upper()
    logging.basicConfig(level=log_level, format="%(levelname)s:VSD: %(message)s")


def main():
    logging.addLevelName(logging.INFO, "\033[1;34m%s\033[1;0m" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))

    app()


if __name__ == "__main__":
    main()
