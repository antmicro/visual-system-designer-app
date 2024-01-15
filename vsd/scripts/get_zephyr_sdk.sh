#!/usr/bin/env sh

set -e

ZEPHYR_SDK_VERSION=$1
ZEPHYR_SDK_INSTALL_DIR=$2

if [ "$1" == "" ] || [ "$2" == "" ]; then
  echo "expected 2 arguments" >&2
  echo "usage: ./get_zephyr_sdk.sh <zephyr-sdk-version> <zephyr-sdk-install-dir>" >&2
  exit 1
fi

curl -kLs https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz | tar xJ --strip 1 -C ${ZEPHYR_SDK_INSTALL_DIR}
cd ${ZEPHYR_SDK_INSTALL_DIR}
./setup.sh -t all -h -c
