#!/usr/bin/env sh

# Copyright (c) 2022-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0


WORKSPACE=$1
EXPECTED_ZEPHYR_VERSION=$2

if [ "$1" = "" ] || [ "$2" = "" ]; then
  echo "expected 2 arguments" >&2
  echo "usage: ./init_zephyr.sh <workspace-dir> <expected-zephyr-version>" >&2
  exit 1
fi

ZEPHYR_DIR=$WORKSPACE/zephyr

if [ ! -d $ZEPHYR_DIR ] ; then
  mkdir -p $ZEPHYR_DIR
  git -C $ZEPHYR_DIR init -q
  git -C $ZEPHYR_DIR remote add origin https://github.com/zephyrproject-rtos/zephyr
fi

CURRENT_ZEPHYR_VERSION=$(git -C $ZEPHYR_DIR rev-parse HEAD 2> /dev/null || echo "none")

if [ "$ZEPHYR_VERSION" != "$EXPECTED_ZEPHYR_VERSION" ] ; then
  git -C $ZEPHYR_DIR fetch -q --depth 1 origin "$EXPECTED_ZEPHYR_VERSION"
  git -C $ZEPHYR_DIR checkout -q FETCH_HEAD
fi

cd $WORKSPACE
if [ ! -d .west ] ; then
  west init -l zephyr
fi

# Always update west, because zpehyr version might have changed.
west update
west zephyr-export
cd -
