# Copyright (c) 2022-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import subprocess
import sys
import typer
import yaml

from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Optional, Annotated
from subprocess import CalledProcessError

from vsd import env
from vsd.utils import git_command, git_commit_sha


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


def get_vsd_resources(workspace):
    url = "https://github.com/antmicro/visual-system-designer-resources.git"
    dest = workspace / "visual-system-designer-resources"

    if dest.exists():
        logging.info("visual-system-designer-resources repo exists")
        return

    logging.info(f"Cloning {url}")
    git_command(["clone", "-q", url, dest], error_msg="Cloning VSD resources failed")


def check_for_modified_files(repo):
    git_command(["diff-files", "--quiet"], repo=repo, error_msg=f"Some files in {repo} are modified. Please stash the changes before updating the repo.")

def update_vsd_resources(workspace):
    resources_repo = workspace / "visual-system-designer-resources"
    if not resources_repo.exists():
        get_vsd_resources(workspace)
        return

    logging.info("Trying to update visual-system-designer-resources repo. ")
    check_for_modified_files(resources_repo)
    git_command(["checkout", "main"], repo=resources_repo, error_msg="Failed to update visual-system-designer-resources repository")
    git_command(["pull", "origin", "main"], repo=resources_repo, error_msg="Failed to update visual-system-designer-resources repository")


def install_zephyr_requirements(zephyr_base):
    zephyr_requirements = str(zephyr_base / "scripts/requirements.txt")
    logging.info(f"Installing Zephyr requirements from: {zephyr_requirements}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "-q", "install", "-r", zephyr_requirements])
    except CalledProcessError as e:
        logging.error(f"Installing Zephyr Python requirements failed. (exitcode: {e.returncode})")
        sys.exit(e.returncode)


def init_zephyr(workspace):
    with open(workspace / "visual-system-designer-resources/zephyr-data/zephyr.version") as f:
        zephyr_version = f.read().strip()

    logging.info(f"Initializing Zephyr workspace in {workspace}")

    init_zephyr_sh = files("vsd.scripts") / "init_zephyr.sh"
    try:
        subprocess.run(["bash", "--", str(init_zephyr_sh), str(workspace), zephyr_version])
    except CalledProcessError as e:
        logging.error(f"Zephyr initialization failed. (exitcode: {e.returncode})")
        sys.exit(e.returncode)

    return workspace / "zephyr"


def update_zephyr(zephyr_dir, zephyr_version):
    current_zephyr_version = git_command(["rev-parse", "HEAD"], repo=zephyr_dir, output=True)

    if current_zephyr_version == zephyr_version:
        return

    logging.info(f"Updating Zephyr to {zephyr_version}")
    check_for_modified_files(zephyr_dir)
    git_command(["fetch", "--depth=1", "origin", zephyr_version], repo=zephyr_dir, error_msg="Failed to update Zephyr repository")
    git_command(["checkout", "FETCH_HEAD"], repo=zephyr_dir, error_msg="Failed to update Zephyr repository")

    logging.info("Updating west workspace")
    try:
        subprocess.check_call(["west", "update"], cwd=zephyr_dir)
    except CalledProcessError as e:
        logging.error(f"Failed to update west workspace. (exitcode: {e.returncode})")
        sys.exit(e.returncode)


def get_zephyr_sdk(sdk_version):
    home = Path(os.environ["HOME"])
    sdk_install_dir = Path(os.environ.get("ZEPHYR_SDK_INSTALL_DIR", home / f"zephyr-sdk-{sdk_version}"))

    def read_sdk_version(dir):
        return (dir / "sdk_version").read_text().strip()

    # If we have correct SDK version we don't need to install it again
    if sdk_install_dir.exists() and sdk_version == read_sdk_version(sdk_install_dir):
        logging.info(f"Found Zephyr SDK v{sdk_version} in {sdk_install_dir}")
        return sdk_install_dir

    # Change install directory to install expected SDK version
    if sdk_install_dir.exists():
        sdk_install_dir = sdk_install_dir.parent / f"zephyr-sdk-{sdk_version}"

    logging.info(f"Installing Zephyr SDK v{sdk_version} in {sdk_install_dir}")
    os.makedirs(sdk_install_dir, exist_ok=True)

    get_zephyr_sdk_sh = files("vsd.scripts") / "get_zephyr_sdk.sh"
    try:
        subprocess.check_call(["bash", "--", str(get_zephyr_sdk_sh), str(sdk_version), str(sdk_install_dir)])
    except CalledProcessError as e:
        logging.error(f"Installing Zephyr SDK failed. (exitcode: {e.returncode})")
        sys.exit(e.returncode)
    return sdk_install_dir


def build_pipeline_manager(workspace):
    pipeline_manager_build_cmd = (
        "pipeline_manager", "build", "server-app",
        "--editor-title", "Visual System Designer",
        "--workspace-directory", workspace / ".pipeline_manager/workspace",
        "--output-directory", workspace / ".pipeline_manager/frontend",
        "--assets-directory", workspace / "visual-system-designer-resources/assets",
        "--favicon-path", workspace / "visual-system-designer-resources/assets/visual-system-designer.svg",
    )
    try:
        subprocess.check_call(pipeline_manager_build_cmd)
    except CalledProcessError as e:
        logging.error(f"Pipeline manager frontend build failed. (exitcode: {e.returncode})")
        sys.exit(e.returncode)


def get_renode_portable(workspace):
    # NOTE: When updating the Renode version here, check if dts2repl shouldn't be updated as well.
    #       dts2repl version is recorded in pyproject.toml.
    renode_version = "1.15.0+20240414gitf47548cef"

    portable_dir = workspace / "renode-portable"
    renode_portable = portable_dir / "renode"

    if renode_portable.exists():
        return renode_portable

    url = f"https://builds.renode.io/renode-{renode_version}.linux-portable-dotnet.tar.gz"

    logging.info(f"Downloading {url} and extractingn into {portable_dir}")

    # XXX: We prefer to do most of initialization in Python, but this operation is simpler when
    #      it's done in shell. `tar` command is way easier to use than `tarfile` module in Python.
    os.makedirs(portable_dir, exist_ok=True)
    subprocess.check_output(f"curl -sL {url} | tar xz --strip=1 -C {portable_dir}", shell=True)

    if not renode_portable.exists():
        logging.error("Renode portable wasn't downloaded.")
        sys.exit(1)

    return renode_portable


def init(dir: Annotated[Path, typer.Argument()] = ".",
         zephyr_base: Optional[Path] = None,
         zephyr_sdk: str = "0.16.3"):
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
            sys.exit(1)

    workspace = dir.resolve()
    zephyr_base = zephyr_base or search_for_zephyr_base(workspace)

    print(f"Init VSD workspace in {workspace}")
    os.makedirs(workspace, exist_ok=True)

    get_vsd_resources(workspace)

    # Initialize Zephyr if it wasn't detected
    if not zephyr_base:
        zephyr_base = init_zephyr(workspace)
    else:
        logging.warning(
            f"Detected Zephyr workspace in {zephyr_base.parent}.\n"
            "If you want to specify different location please provide path to initialized Zephyr "
            "workspace using `--zephyr-base` option."
        )

    install_zephyr_requirements(zephyr_base)
    build_pipeline_manager(workspace)

    zephyr_sdk_install_dir = get_zephyr_sdk(zephyr_sdk)
    renode_portable_path = get_renode_portable(workspace)

    # Save paths that will be used later by vsd app
    vars = {}
    vars["PYRENODE_BIN"] = str(renode_portable_path.resolve())
    vars["PYRENODE_RUNTIME"] = "coreclr"
    vars["ZEPHYR_SDK_INSTALL_DIR"] = str(zephyr_sdk_install_dir.resolve())
    vars["ZEPHYR_BASE"] = str(zephyr_base.resolve())
    with open(workspace / "vsd-env.yml", "w") as f:
        yaml.dump(vars, f)

    os.environ["VSD_WORKSPACE"] = str(workspace)
    vsd_workspace_info()

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
    print(f"Workspace: {workspace}")
    print("-----------------------")

    max_len = max(len(x) for x in env.get_env().keys())
    for k,v in env.get_env().items():
        print(f"{k:<{max_len}}: {v}")

    print("-----------------------")
    print(f"       Zephyr commit: {git_commit_sha(env.get_var('ZEPHYR_BASE'))}")
    print(f"VSD resources commit: {git_commit_sha(workspace / 'visual-system-designer-resources')}")

    try:
        renode_version = subprocess.check_output([env.get_var("PYRENODE_BIN"), "--version"])
    except CalledProcessError as e:
        logging.error(f"Failed to get Renode version (exitcode: {e.returncode})")
        sys.exit(e.returncode)
    except Exception as e:
        logging.error(f"Failed to run `renode --version` command: {e}")
        sys.exit(1)

    print("-----------------------")
    print(renode_version.decode().strip())


class UpdateChoices(StrEnum):
    ALL = "all"
    ZEPHYR = "zephyr"
    RESOURCES = "resources"


@env.setup_env
def vsd_update_workspace(component: Annotated[UpdateChoices, typer.Argument()] = UpdateChoices.ALL,
                         zephyr_base: Optional[Path] = None,
                         zephyr_sdk: str = "0.16.3"):
    workspace = Path(env.get_workspace())

    if component in [UpdateChoices.ALL, UpdateChoices.RESOURCES]:
        update_vsd_resources(workspace)

    if component in [UpdateChoices.ALL, UpdateChoices.ZEPHYR]:
        zephyr_version = (workspace / "visual-system-designer-resources/zephyr-data/zephyr.version").read_text().strip()
        zephyr_dir = Path(env.get_var("ZEPHYR_BASE"))
        update_zephyr(zephyr_dir, zephyr_version)
