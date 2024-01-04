#!/usr/bin/env python

# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys
import typer

from vsd.build import build_zephyr, prepare_zephyr_board
from vsd.backend import start_vsd_app
from vsd.simulate import prepare_renode_files, simulate

app = typer.Typer(no_args_is_help=True, add_completion=False)

app.command()(prepare_zephyr_board)

app.command()(build_zephyr)

app.command()(prepare_renode_files)

app.command()(simulate)

app.command("run")(start_vsd_app)


def main():
    logging.addLevelName(logging.INFO, "\033[1;34m%s\033[1;0m" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))

    if sys.prefix == sys.base_prefix:
        logging.error("Not running in the VSD virtualenv. Please setup environment first.")
        sys.exit(1)

    if 'ZEPHYR_BASE' not in os.environ or os.environ["ZEPHYR_BASE"] == "":
        logging.error("ZEPHYR_BASE not defined. Please setup environment first.")
        sys.exit(1)

    app()


if __name__ == "__main__":
    main()
