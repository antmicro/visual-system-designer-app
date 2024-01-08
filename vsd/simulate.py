# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import argparse
import logging
import os
import re
import sys

from dts2repl import dts2repl
from importlib.resources import files
from pathlib import Path


def _prepare_from_template(format, template, dest):
    with open(template) as f:
        template = f.read()
    with open(dest, "w") as f:
        f.write(template.format(**format))


def _prepare_repl(dts_path, repl_path):
    repl = dts2repl.generate(argparse.Namespace(filename=str(dts_path)))
    if repl == '':
        return False
    with open(repl_path, 'w') as f:
        f.write(repl)
    return True


def _find_chosen(name, dts_path):
    with open(dts_path, 'r') as f:
        dts = f.read()
    console_m = re.search(f'{name} = &(.+);', dts)
    if not console_m:
        return None
    return console_m.group(1)


def prepare_renode_files(board_name: str,
                         templates_dir: Path = files('vsd.templates').joinpath("")):
    workspace = Path(os.environ.get("VSD_WORKSPACE"))
    builds_dir = workspace / 'builds' / board_name
    dts_path = builds_dir / "zephyr/zephyr.dts"
    elf_path = builds_dir / "zephyr/zephyr.elf"
    resc_path = builds_dir / f"{board_name}.resc"
    repl_path = builds_dir / f"{board_name}.repl"

    format = {
        'board_name': board_name,
        'resc_path': resc_path.absolute(),
        'repl_path': repl_path.absolute(),
        'elf_path': elf_path.absolute(),
    }

    zephyr_console = _find_chosen("zephyr,console", dts_path)
    if zephyr_console:
        format['console'] = zephyr_console

    try:
        _prepare_from_template(format, templates_dir / "run.resc", resc_path)
    except KeyError as e:
        logging.error(f"Haven't found value to create renode files: {e}")
        return 1

    ret = _prepare_repl(dts_path, repl_path)
    if not ret:
        logging.error("Failed to create REPL file")
        return 1

    logging.info(f"Renode files for board {board_name} are ready in {builds_dir}")
    return 0


def prepare_simulation(board_name, elf_path, repl_path):
    from pyrenode3.wrappers import Emulation
    emu = Emulation()
    machine = emu.add_mach('machine0')
    machine.load_repl(str(repl_path.absolute()))
    machine.load_elf(str(elf_path.absolute()))
    return emu, machine


def register_led_callback(machine, source, repl_label, callback):
    from Antmicro.Renode.Peripherals.Miscellaneous import ILed
    led = ILed(machine.internal[f"sysbus.{source}.{repl_label}"])
    led.StateChanged += (callback)


class UTF8Decoder:
    def __init__(self):
        self._utf8_chars_left = 0
        self._utf8_buffer = bytearray()

    def wrap_callback(self, inner_cb):
        def callback(char):
            UTF8_2_MASK = 0b11100000
            UTF8_3_MASK = 0b11110000
            UTF8_1      = 0b10000000
            UTF8_2      = 0b11000000
            UTF8_3      = 0b11100000

            if char & UTF8_3_MASK == UTF8_3:
                self._utf8_chars_left = 2
                self._utf8_buffer.append(char)
                return

            if char & UTF8_2_MASK == UTF8_2:
                self._utf8_chars_left = 1
                self._utf8_buffer.append(char)
                return

            if char & UTF8_1:
                self._utf8_chars_left -= 1
                assert self._utf8_chars_left >= 0

                self._utf8_buffer.append(char)

                if self._utf8_chars_left == 0:
                    inner_cb(self._utf8_buffer.decode())
                    self._utf8_buffer = bytearray()
            else:
                # The char isn't encoded so we can just redirect it.
                inner_cb(chr(char))
        return callback


def register_uart_callback(uart, callback):
    uart.CharReceived += (callback)


def get_all_uarts(machine):
    from Antmicro.Renode.Peripherals.UART import IUART
    from pyrenode3 import wrappers
    uarts = list(machine.GetPeripheralsOfType[IUART]())
    return [(u, wrappers.Peripheral(u).name) for u in uarts]


class ConsoleCallbackPool():
    def __init__(self):
        self.active_uart = None

    def create_callback(self, uart, active=False):
        decoder = UTF8Decoder()
        if active:
            if self.active_uart is not None:
                raise Exception("Can't set more than one active consoles!")

            self.active_uart = uart
            return decoder.wrap_callback(lambda c: print(c, end=''))

        # If active console is already set, then just ignore all characters.
        if self.active_uart is not None:
            return (lambda c: None)

        @decoder.wrap_callback
        def console_callback(char):
            if self.active_uart is None:
                self.active_uart = uart
            # Print only when active uart matches the current one
            if self.active_uart is uart:
                print(char, end='')

        return console_callback


def simulate(board_name: str):
    workspace = Path(os.environ.get("VSD_WORKSPACE"))
    builds_dir = workspace / 'builds' / board_name
    repl_path = builds_dir / f"{board_name}.repl"
    elf_path = builds_dir / "zephyr/zephyr.elf"
    dts_path = builds_dir / "zephyr/zephyr.dts"

    try:
        emu, machine = prepare_simulation(board_name, elf_path, repl_path)
    except Exception as e:
        print(f"Simulation can't be prepared using {repl_path} and {elf_path}!")
        print(f"\n{e}")
        sys.exit(1)

    callback_pool = ConsoleCallbackPool()

    all_uarts = get_all_uarts(machine)
    if len(all_uarts) > 0:
        zephyr_console = _find_chosen('zephyr,console', dts_path)
        for uart, name in get_all_uarts(machine):
            register_uart_callback(uart, callback_pool.create_callback(uart, active=(name == zephyr_console)))
    else:
        print("Runing without console output")

    print(f"Starting simulation on {board_name}. Press Ctrl+C to quit.")
    print("-----------------------------------")
    emu.StartAll()

    try:
        # Just wait for signal
        while True:
            pass
    finally:
        emu.clear()
        print("Exiting...")
