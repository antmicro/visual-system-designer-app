#!/usr/bin/env python

# Copyright (c) 2023-2024 Antmicro
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import random
import re
import sys
import typer

from colorama import Fore, Style
from enum import IntEnum
from pathlib import Path
from texttable import Texttable
from threading import Event
from typing import List

from vsd import build
from vsd import env
from vsd import simulate
from vsd.graph import Node
from vsd.specification import Specification


thermometers = ["si7210", "tmp108"]

configurations = [
    "soc",
    "soc+led",
    "soc+si7210",
    "soc+tmp108",
]

test_str = {
    "soc": "Blinky and temperature example",
    "soc+led": "LED led_0 state: 1",
    "soc+si7210": "silabs_si7210@18:",
    "soc+tmp108": "ti_tmp108@30:",
}

i2c_addresses = {
    "si7210": 0x18,
    "tmp108": 0x30,
}


class Status(IntEnum):
    NONE = 0
    BAD_SPEC = 1
    BAD_NAME = 2
    BAD_INTERFACE = 3
    CONFIG = 4
    GENERATED = 5
    BUILT = 6
    SIMERROR = 7
    TIMEOUT = 8
    OK = 9

    @classmethod
    def print_legend(cls):
        descr = {
            cls.OK: "Simulation succeeded.",
            cls.TIMEOUT: "Simulation timeout.",
            cls.SIMERROR: "Simulation failed.",
            cls.BUILT: "Zephyr built successfuly.",
            cls.GENERATED: "Zephyr board generated.",
            cls.CONFIG: "Configuration created",
            cls.BAD_INTERFACE: "Error when looking for specified interface in node",
            cls.BAD_NAME: "Error when looking for Renodepedia name in node",
            cls.BAD_SPEC: "Error when looking for node in components specification",
            cls.NONE: "There is no information about given configuration",
        }
        print("Status string legend:")
        for stat in cls:
            print(f" - {stat.name} -- {descr[stat]}")


def red(text):
    return Fore.RED + (text or '') + Style.RESET_ALL


def green(text):
    return Fore.GREEN + (text or '') + Style.RESET_ALL


class NodeSpecNotFound(Exception):
    pass


class InterfaceNotFound(Exception):
    pass


class RenodepediaNameNotFound(Exception):
    pass


def find_soc_interface(soc, if_type, spec):
    spec_node = spec.get_node_spec(soc)
    if not spec_node:
        raise NodeSpecNotFound(f"Node '{soc}' not found in specification")

    for interface in spec_node["interfaces"]:
        if if_type == interface.get("type"):
            return interface["name"]
    raise InterfaceNotFound(f"Interface of type '{if_type}' not found in '{soc}'")


def get_soc_rdp_name(soc, spec):
    spec_node = spec.get_node_spec(soc)
    if not spec_node:
        raise NodeSpecNotFound(f"Node '{soc}' not found in specification")

    if "urls" in spec_node and "rdp" in spec_node["urls"]:
        rdp_link = spec_node["urls"]["rdp"]
        return rdp_link.split("/")[-1]
    raise RenodepediaNameNotFound(f"Can't create rdp name for node '{soc}'")


node_id = 0


def create_fake_node_connection(name, soc_iface, node_iface, spec, address):
    global node_id
    node = {
        "name": name,
        "instanceName": f"{name}_{node_id}",
        "id": str(node_id),
        "properties": [],
        "interfaces": [],
    }
    node_id += 1
    node["properties"].append({
        "name": f"address ({node_iface})",
        "value": hex(address),
    })
    return (soc_iface, node_iface, Node(node, spec))


def prepare_single_config(soc, config, spec):
    connections = []
    board_name = re.sub(r"[\s+-]+", "_", soc + config[3:])
    soc_name = get_soc_rdp_name(soc, spec)

    for tmp in thermometers:
        if_name = find_soc_interface(soc, "i2c", spec)
        if tmp in config:
            connections.append(create_fake_node_connection(tmp, if_name, "i2c", spec, i2c_addresses[tmp]))

    if "led" in config:
        if_name = find_soc_interface(soc, "gpio", spec)
        connections.append(create_fake_node_connection("LED", if_name, "gpio", spec, 0x0))

    return (soc_name, board_name, connections)


class LineTester():
    def __init__(self, line_test_cb):
        self.acc_event = Event()
        self.line_test_cb = line_test_cb
        self.line = []

    def get_callback(self):
        def callback(char):
            self.line.append(char)
            if char == 10:  # Line Feed
                line = bytearray(self.line).decode()
                if self.line_test_cb(line):
                    self.acc_event.set()
                    return
                self.line = []
        return callback

    def wait(self, timeout):
        acc = self.acc_event.wait(timeout=timeout)
        if acc:
            return Status.OK
        else:
            return Status.TIMEOUT


def run_test(board_name, build_dir, config):
    repl_path = build_dir / f"{board_name}.repl"
    elf_path = build_dir / "zephyr/zephyr.elf"
    dts_path = build_dir / "zephyr/zephyr.dts"

    try:
        emu, machine = simulate.prepare_simulation(board_name, elf_path, repl_path)
    except Exception as e:
        print(f"Simulation can't be prepared using {repl_path} and {elf_path}!", file=sys.stderr)
        print(f"\n{e}", file=sys.stderr)
        return Status.SIMERROR

    def test_line(line):
        if re.search(test_str[config], line):
            return True
        return False

    tester = LineTester(test_line)

    zephyr_console = simulate._find_chosen("zephyr,console", dts_path)

    for uart, uart_name in simulate.get_all_uarts(machine):
        if uart_name == zephyr_console:
            simulate.register_uart_callback(
                uart,
                tester.get_callback()
            )
    try:
        emu.StartAll()
        status = tester.wait(3)
    except Exception as e:
        logging.error(f"{board_name}: {e}")
        status = Status.SIMERROR
    finally:
        emu.clear()

    return status


def validate(soc, config, spec, app, workspace, zephyr_base):
    try:
        soc_name, board_name, connections = prepare_single_config(soc, config, spec)
    except NodeSpecNotFound:
        return Status.BAD_SPEC
    except RenodepediaNameNotFound:
        return Status.BAD_NAME
    except InterfaceNotFound:
        return Status.BAD_INTERFACE

    status = Status.CONFIG

    board_dir = build.prepare_zephyr_board_dir(board_name, soc_name, connections, workspace)
    if board_dir:
        status = Status.GENERATED
    else:
        return status

    build_ret, build_dir = build.build_zephyr(board_name, app, quiet=True)
    if build_ret == 0:
        status = Status.BUILT
    else:
        return status

    prep_ret = simulate.prepare_renode_files(board_name)
    if prep_ret != 0:
        return status

    return run_test(board_name, build_dir, config)


app = typer.Typer()

@app.command()
@env.setup_env
def single_soc(soc_name: str, application: Path = Path("demo/blinky-temperature")):
    zephyr_base = Path(env.get_var("ZEPHYR_BASE"))
    workspace = Path(env.get_workspace())

    specification = Specification(workspace / "visual-system-designer-resources/components-specification.json")

    for config in configurations:
        status = validate(soc_name, config, specification, application, workspace, zephyr_base)
        print(f"{config}: {status.name}")


@env.setup_env
def validate_socs_list(socs, output_f, application, specification = None):
    zephyr_base = Path(env.get_var("ZEPHYR_BASE"))
    workspace = Path(env.get_workspace())

    if not specification:
        specification = Specification(workspace / "visual-system-designer-resources/components-specification.json")

    results = {}
    for soc_name in socs:
        print(f"{soc_name}")
        results[soc_name] = {}
        for config in configurations:
            status = validate(soc_name, config, specification, application, workspace, zephyr_base)
            results[soc_name][config] = status.name
            print(f"  {config}: {status.name}")

    with open(output_f, "w") as f:
        json.dump(results, f, indent=4, sort_keys=True)
    print(f"Results saved to {output_f}")


@app.command()
def soc_list(socs_list: Path,
             output: Path = Path("results.json"),
             application: Path = Path("demo/blinky-temperature")):

    with open(socs_list) as f:
        socs = f.read().strip().splitlines()
    validate_socs_list(socs, output, application)


@app.command()
@env.setup_env
def all_socs(output: Path = Path("results.json"),
             application: Path = Path("demo/blinky-temperature"),
             chunk_total: int = 1,
             chunk_id: int = 0,
             seed: str = None):

    workspace = Path(env.get_workspace())
    specification = Specification(workspace / "visual-system-designer-resources/components-specification.json")

    all_socs = specification.get_socs()

    if seed:
        print(f"Rand seed: {seed}")
        random.seed(seed)
        random.shuffle(all_socs)

    chunk_len = -(-len(all_socs) // chunk_total)  # Rounded up chunk size
    chunk_start = chunk_id * chunk_len
    chunk_end = chunk_id * chunk_len + chunk_len

    print(f"Chunk size: {chunk_len}")
    print(f"Chunk boundaries: {chunk_start}-{chunk_end}")

    socs = all_socs[chunk_start:chunk_end]
    validate_socs_list(socs, output, application, specification)


@app.command()
def print_results(results: List[Path], output: Path = None):
    all_results = {}
    for res in results:
        with open(res) as f:
            all_results.update(json.load(f))

    if output:
        with open(output, "w") as f:
            json.dump(all_results, f, indent=4, sort_keys=True)

    configs = sorted(list(all_results.values())[0].keys())

    table = Texttable(max_width=160)
    table.set_deco(Texttable.BORDER | Texttable.HEADER | Texttable.VLINES)
    table.header(["id", "soc name"] + configs)
    table.set_cols_align(["c", "l"] + ["c"] * len(configs))

    totals = dict.fromkeys(configs, 0)
    for i, (soc, res) in enumerate(sorted(all_results.items(), key=lambda t: t[0].lower())):
        output = f"| {i:>3} | {soc:<20} |"
        for config in configs:
            if res[config] == "OK":
                totals[config] += 1
        table.add_row([i, soc] + [res[c] for c in configs])

    print(table.draw())

    summary_table = Texttable()
    summary_table.set_deco(Texttable.BORDER | Texttable.HEADER | Texttable.VLINES)
    summary_table.header([""] + configs)
    summary_table.set_cols_align(["r"] + ["c"] * len(configs))


    def get_percent(count, total):
        return f"{count / total * 100:.0f}%"
        totals[config]


    print("\nSummary of successful targets")
    summary_table.add_row(["total"] + [totals[c] for c in configs])
    summary_table.add_row(["percent"] + [get_percent(totals[c], len(all_results)) for c in configs])

    print(summary_table.draw())

    print("")
    Status.print_legend()


@app.command()
def show_changes(prev_results: Path, new_results: Path, fail_on_regression: bool = False):
    with open(prev_results) as f:
        prev_results = json.load(f)
    with open(new_results) as f:
        new_results = json.load(f)

    new = new_results.keys() - prev_results.keys()
    print(f"--- New SoCs ({len(new)}) ---")
    for soc in new:
        print(f" {soc}:")
        for conf, res in new_results[soc].items():
            print(green(f" {conf:>11}: NONE -> {res}"))
    print("")

    missing = prev_results.keys() - new_results.keys()
    print(f"--- Missing SoCs ({len(missing)}) ---")
    for soc in missing:
        print(f" {soc}:")
        for conf, res in prev_results[soc].items():
            print(red(f" {conf:>11}: {res} -> NONE"))
    print("")

    regressions = 0
    changes = []

    for k in prev_results.keys() & new_results.keys():
        res1 = prev_results[k]
        res2 = new_results[k]
        stats = []
        for c in res1.keys() | res2.keys():
            res1_outcome = Status[res1.get(c, "NONE")]
            res2_outcome = Status[res2.get(c, "NONE")]

            if res1_outcome > res2_outcome:
                regressions += 1
                color = red
            elif res1_outcome < res2_outcome:
                color = green
            else:
                continue
            stats.append(color(f"{c:>11}: {res1_outcome.name} ({res1_outcome}) -> {res2_outcome.name} ({res2_outcome})"))

        if len(stats):
            changes.append((k, stats))

    print(f"--- Changes in individual SoCs ({len(changes)}) ---")
    for soc, stats in changes:
        print(f" {soc}:")
        for stat in stats:
            print("  ", stat)

    print("")
    Status.print_legend()


    if regressions > 0 and fail_on_regression:
        exit(1)


if __name__ == "__main__":
    app()
