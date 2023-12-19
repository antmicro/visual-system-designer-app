#!/usr/bin/env python

# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import atexit
import logging
import os
import sys
import typer

from multiprocessing import Process
from pathlib import Path
from time import sleep

from pipeline_manager.scripts.run import script_run as pm_main
from vsd.build import build_zephyr, prepare_zephyr_board
from vsd.backend import start_vsd_backend
from vsd.simulate import prepare_renode_files, simulate

app = typer.Typer(no_args_is_help=True, add_completion=False)

app.command()(prepare_zephyr_board)

app.command()(build_zephyr)

app.command()(prepare_renode_files)

app.command()(simulate)

@app.command("run")
def start_vsd_app(application: Path = Path("demo/blinky-temperature"),
                  workspace: Path = Path("workspace"),
                  templates_dir: Path = Path("renode-templates"),
                  website_host: str = "127.0.0.1",
                  website_port: int = 9000,
                  vsd_backend_host: str = "127.0.0.1",
                  vsd_backend_port: int = 5000,
                  verbosity: str = "INFO"):

    logging.basicConfig(level=verbosity, format="%(levelname)s:VSD backend:\t%(message)s")

    frontend_dir = workspace / ".pipeline_manager/frontend"
    app_workspace = workspace / ".pipeline_manager/workspace"

    pm_args = (
        "pipeline_manager",  # The first argument must be a program name.
        "--frontend-directory", str(frontend_dir),
        '--workspace-directory', str(app_workspace),
        "--backend-host", website_host,
        "--backend-port", str(website_port),
        "--tcp-server-host", vsd_backend_host,
        "--tcp-server-port", str(vsd_backend_port),
        "--verbosity", "INFO",
    )
    pm_proc = Process(target=pm_main, args=[pm_args])
    pm_proc.start()

    def wait_for_pm():
        pm_proc.join()
        logging.info("Pipeline manager server closed. Exiting...")

    atexit.register(wait_for_pm)
    sleep(0.5)

    # XXX: This function won't return.
    start_vsd_backend(vsd_backend_host, vsd_backend_port, workspace, application, templates_dir)


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
