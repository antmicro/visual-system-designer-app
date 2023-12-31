#!/usr/bin/env bash

# Copyright (c) 2023 Antmicro
# SPDX-License-Identifier: Apache-2.0

set -e

# Default values for variables
: ${WORKSPACE:=workspace}
: ${VSDENV:=$WORKSPACE/.vsdenv}
: ${ZEPHYR_SDK_VERSION:=0.16.3}
: ${ZEPHYR_SDK_INSTALL_DIR:=$HOME/zephyr-sdk-${ZEPHYR_SDK_VERSION}}
: ${PYRENODE_ARCH_PKG:=$WORKSPACE/renode-latest.pkg.tar.xz}

create_venv() {
  if [[ ! -d $VSDENV ]]; then
    echo "INFO: Creating Python virtualenv in the $VSDENV directory."
    python3 -m venv $VSDENV
  else
    echo "INFO: Existing venv $VSDENV found, assuming it's OK to use."
    echo "INFO: If you run into any issues with the venv, removing the $VSDENV directory will recreate one on the next run."
  fi
}

# TODO: check with tmux.
# Supposedly, this is a bad way since you can get a false positive with a
# new shell (not in a venv) spawned from a tmux shell in a venv
if [[ "$VIRTUAL_ENV" == "" ]] ; then
  create_venv
  source $VSDENV/bin/activate
else
  echo "INFO: Already in a venv. If not sure if you have the right one, you can use deactivate and run again."
fi

clone_or_update() {
  REPO=$1
  BRANCH=${2:-main}
  if [[ ! -d $WORKSPACE/$REPO ]] ; then
    git clone https://github.com/antmicro/$REPO.git -b $BRANCH $WORKSPACE/$REPO
  else
    echo "INFO: Updating '$WORKSPACE/$REPO'"
    cd $WORKSPACE/$REPO
    git checkout -q $BRANCH && git pull -q
    cd - > /dev/null
  fi
}

get_dependencies() {
  clone_or_update visual-system-designer-resources
  clone_or_update kenning-pipeline-manager
  clone_or_update kenning-pipeline-manager-backend-communication
}

install_requirements() {
  if [[ ! -e $VSDENV/installed ]]; then
    echo -n "INFO: Installing VSD Python requirements"
    pip3 install -r requirements.txt
    pip3 install -e $WORKSPACE/kenning-pipeline-manager
    pip3 install -e $WORKSPACE/kenning-pipeline-manager-backend-communication
    touch $VSDENV/installed
  else
    echo "INFO: VSD Python requirements are marked as installed."
    echo "INFO: Remove $VSDENV/installed to force reinstall on next run."
  fi
}

get_zephyr() {
  EXPECTED_ZEPHYR_VERSION="$(cat $WORKSPACE/visual-system-designer-resources/zephyr-data/zephyr.version)"
  if [[ ! -d $WORKSPACE/zephyr ]] ; then
    mkdir -p $WORKSPACE/zephyr
    cd $WORKSPACE/zephyr
    git init
    git remote add origin https://github.com/zephyrproject-rtos/zephyr
    git fetch --depth 1 origin "$EXPECTED_ZEPHYR_VERSION"
    git checkout FETCH_HEAD
    cd -
  else
    echo "INFO: Zephyr workspace with zephyr inside found in the $WORKSPACE directory."
    ZEPHYR_VERSION="$(git -C $WORKSPACE/zephyr rev-parse HEAD)"
    if [[ "$ZEPHYR_VERSION" != "$EXPECTED_ZEPHYR_VERSION" ]] ; then
      echo "INFO: Wrong zephyr version. Trying to checkout to $EXPECTED_ZEPHYR_VERSION..."
      git -C $WORKSPACE/zephyr checkout "$EXPECTED_ZEPHYR_VERSION"
      echo "INFO: Done."
    else
      echo "INFO: Zephyr version is $EXPECTED_ZEPHYR_VERSION as expected."
    fi
  fi
  if [[ -d $WORKSPACE/.west ]] ; then
    echo "INFO: West seems to be initialized in $WORKSPACE."
    echo "INFO: If you want to west init/update + install Zephyr deps, delete $WORKSPACE/.west and try again."
  else
    cd $WORKSPACE
    echo "INFO: Initializing Zephyr."
    west init -l zephyr
    west update
    west zephyr-export
    echo "INFO: Installing Zephyr's Python requirements."
    pip3 install -r zephyr/scripts/requirements.txt
    cd -
  fi
}

get_zephyr_sdk() {
  if [[ -d ${ZEPHYR_SDK_INSTALL_DIR} ]] && [[ "$(cat ${ZEPHYR_SDK_INSTALL_DIR}/sdk_version)" == "${ZEPHYR_SDK_VERSION}" ]] ; then
    echo "INFO: Zephyr SDK found: ${ZEPHYR_SDK_INSTALL_DIR}"
    return
  else
    # Prepare new directory for SDK
    ZEPHYR_SDK_INSTALL_DIR=$(dirname ${ZEPHYR_SDK_INSTALL_DIR})/zephyr-sdk-${ZEPHYR_SDK_VERSION}
    mkdir -p ${ZEPHYR_SDK_INSTALL_DIR}
  fi

  echo "INFO: Installing Zephyr SDK in ${ZEPHYR_SDK_INSTALL_DIR}"
  curl -kLs https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz | tar xJ --strip 1 -C ${ZEPHYR_SDK_INSTALL_DIR}
  CWD=$(pwd)
  cd ${ZEPHYR_SDK_INSTALL_DIR}
  ./setup.sh -t all -h -c
  cd $CWD
}

build_pipeline_manager() {
  pipeline_manager build server-app \
    --workspace-directory $WORKSPACE/.pipeline_manager/workspace \
    --output-directory $WORKSPACE/.pipeline_manager/frontend \
    --assets-directory $WORKSPACE/visual-system-designer-resources/assets \
    --favicon-path $WORKSPACE/visual-system-designer-resources/assets/visual-system-designer.svg
}

get_renode_arch_pkg() {
    if [[ -f $PYRENODE_ARCH_PKG ]] ; then
      echo "INFO: Renode package available in $WORKSPACE."
      echo "INFO: If you want to redownload it, remove $PYRENODE_ARCH_PKG and try again."
    else
      echo "INFO: downloading $PYRENODE_ARCH_PKG from https://builds.renode.io/renode-latest.pkg.tar.xz"
      curl -kLs --output $PYRENODE_ARCH_PKG https://builds.renode.io/renode-latest.pkg.tar.xz
    fi
}

generate_env_script() {
  cat > $ENV_FILE <<EOF
# Autogenerated configuration file
WORKSPACE=$WORKSPACE
VSDENV=$VSDENV
ZEPHYR_SDK_INSTALL_DIR=$ZEPHYR_SDK_INSTALL_DIR
PYRENODE_ARCH_PKG=$PYRENODE_ARCH_PKG
source $VSDENV/bin/activate
source $WORKSPACE/zephyr/zephyr-env.sh
export ZEPHYR_SDK_INSTALL_DIR
export PYRENODE_ARCH_PKG
EOF
}

#TODO: allow for individual running of commands, because why not
get_dependencies
install_requirements
get_zephyr
get_zephyr_sdk
build_pipeline_manager
get_renode_arch_pkg

ENV_FILE=$WORKSPACE/vsd-env.sh
generate_env_script

echo "Configuration created in '$WORKSPACE' directory. Source the '$ENV_FILE' to activate VSD environment."
