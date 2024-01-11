import logging
import os
import subprocess
import typer
import yaml

from importlib.resources import files
from pathlib import Path
from typing_extensions import Annotated


def init(dir: Annotated[Path, typer.Argument()] = "."):
    """
    Initialize VSD workspace.
    """
    if "VSD_WORKSPACE" in os.environ:
        env_ws = Path(os.environ.get("VSD_WORKSPACE")).resolve()
        if env_ws != dir.resolve():
            logging.error(
                f"The VSD workspace is already initialized in {env_ws}.\n"
                "If you want to initialize new workspace please unset VSD_WORKSPACE variable."
            )
            exit(1)

    workspace = dir.resolve()

    print(f"Init VSD workspace in {workspace}")

    logging.warning("Using legacy setup script")
    legacy_setup = files('vsd.scripts') / 'setup.sh'

    os.environ["WORKSPACE"] = str(workspace)
    ret = subprocess.run(["bash", str(legacy_setup)])
    if ret.returncode != 0:
        logging.error("Legacy setup fail")
        exit(1)

    # XXX: Parse old vsd-env.sh file to find proper paths there and create vsd-env.yaml
    with open(workspace / "vsd-env.sh") as f:
        lines = filter(lambda x: "=" in x, f.readlines())

    needed_vars = ("PYRENODE_ARCH_PKG", "ZEPHYR_SDK_INSTALL_DIR")

    vars = (ln.strip().split("=") for ln in lines)
    vars = {k: v for [k, v] in vars if k in needed_vars}

    vars["ZEPHYR_BASE"] = str(workspace / 'zephyr')

    # Dump variables that will be needed later when running vsd app
    with open(workspace / "vsd-env.yml", 'w') as f:
        yaml.dump(vars, f)

    if workspace != Path.cwd():
        logging.warning(
            "VSD workspace initialized in directory which is not cwd.\n"
            "To make sure that proper directory will be used as VSD workspace please export following variable:\n"
            f"\texport VSD_WORKSPACE={workspace}"
        )


def vsd_workspace_info():
    """
    Display info about initialized components of VSD workspace.
    """
    workspace = Path(os.environ.get('VSD_WORKSPACE'))

    print(f"VSD workspace: {workspace}")
    with open(workspace / "vsd-env.yml") as f:
        vars = yaml.safe_load(f)

    for k, v in vars.items():
        print(f"{k}: {v}")
