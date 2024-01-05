import logging
import os
import subprocess
import typer
import yaml

from importlib.resources import files
from pathlib import Path
from typing import Optional, Annotated

from vsd import env


def search_for_zephyr_base(workspace):
    # When zephyr is initialized in workspace, use it.
    workspace_zephyr = workspace / "zephyr"
    if workspace_zephyr.exists():
        return workspace_zephyr.resolve()

    if "ZEPHYR_BASE" in os.environ:
        logging.warning(
            f"Detected existing Zephyr workspace because ZEPHYR_BASE is set to {os.environ['ZEPHYR_BASE']}.\n"
            "If you don't want to use it unset ZEPHYR_BASE variable."
        )
        return Path(os.environ["ZEPHYR_BASE"])

    # Search for '.west' directory in all directories above.
    d = workspace
    while d != d.parent:
        if d.exists() and ".west" in os.listdir(d):
            logging.warning(
                f"Detected existing Zephyr workspace because {d}/.west directory exists.\n"
            )
            return d / "zephyr"
        d = d.parent
    return None


def init(dir: Annotated[Path, typer.Argument()] = ".", zephyr_base: Optional[Path] = None):
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
    zephyr_base = zephyr_base or search_for_zephyr_base(workspace)

    print(f"Init VSD workspace in {workspace}")
    os.makedirs(workspace, exist_ok=True)

    logging.warning("Using legacy setup script")
    legacy_setup = files("vsd.scripts") / "setup.sh"

    os.environ["WORKSPACE"] = str(workspace)

    # Initialize all components besides zephyr
    ret = subprocess.run(["bash", str(legacy_setup)])
    if ret.returncode != 0:
        logging.error("Legacy setup fail")
        exit(ret.returncode)


    # Initialize Zephyr if it wasn't detected
    if not zephyr_base:
        logging.info(f"Initializing Zephyr in {workspace}")
        ret = subprocess.run(["bash", str(legacy_setup), "only-zephyr"])
        if ret.returncode != 0:
            logging.error("Failed to initialize Zephyr.")
            exit(ret.returncode)
        zephyr_base = workspace / "zephyr"
    else:
        logging.warning(
            f"Detected Zephyr workspace in {zephyr_base.parent}.\n"
            "If you want to specify different location please provide path to initialized Zephyr "
            "workspace using `--zephyr-base` option."
        )

    # XXX: Parse old vsd-env.sh file to find proper paths there and create vsd-env.yaml
    with open(workspace / "vsd-env.sh") as f:
        lines = filter(lambda x: "=" in x, f.readlines())

    needed_vars = ("PYRENODE_ARCH_PKG", "ZEPHYR_SDK_INSTALL_DIR")

    vars = (ln.strip().split("=") for ln in lines)
    vars = {k: v for [k, v] in vars if k in needed_vars}

    vars["ZEPHYR_BASE"] = str(zephyr_base.resolve())

    # Dump variables that will be needed later when running vsd app
    with open(workspace / "vsd-env.yml", "w") as f:
        yaml.dump(vars, f)

    if workspace != Path.cwd():
        logging.warning(
            "VSD workspace initialized in directory which is not cwd.\n"
            "To make sure that proper directory will be used as VSD workspace please export following variable:\n"
            f"\texport VSD_WORKSPACE={workspace}"
        )


@env.setup_env
def vsd_workspace_info():
    """
    Display info about initialized components of VSD workspace.
    """
    workspace = Path(env.get_workspace())

    print(f"VSD workspace: {workspace}")
    with open(workspace / "vsd-env.yml") as f:
        vars = yaml.safe_load(f)

    for k, v in vars.items():
        print(f"{k}: {v}")
