# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import sys
import yaml

from pathlib import Path

from vsd import env
from vsd.graph import Graph
from vsd.specification import Specification


def _prep_kconfig_board(board_name, configs):
    content = ""
    content += f"config BOARD_{board_name.upper()}\n"
    content += f"\tbool \"{board_name}\"\n"
    if "select" in configs:
        for flag in configs["select"]:
            content += f"\tselect {flag}\n"
    soc_name = configs["board_socs"][0]["name"]
    content += f"\tselect SOC_{soc_name.upper()}"
    return content


def _prep_defconfig(configs, zephyr_dir):
    with open(zephyr_dir / configs["defconfig_file"]) as f:
        defconfig = f.read()

    if "remove_defconfig_flags" in configs:
        for flag in configs["remove_defconfig_flags"]:
            defconfig = re.sub(f'{flag}=y\n', '', defconfig)

    if "add_defconfig_flags" in configs:
        defconfig += "\n".join(configs["add_defconfig_flags"]) + "\n"

    return defconfig


def _filter_nodes(connections, filter_fn):
    leds, other = [], []
    for conn in connections:
        _, _, component = conn
        if filter_fn(component):
            leds.append(conn)
        else:
            other.append(conn)
    return leds, other


def _enable_iface(interface):
    snippet = f"&{interface} " + "{\n"
    snippet += '\tstatus = "okay";\n'
    snippet += "};\n"
    return snippet


def _prep_leds(leds):
    snippet = "#include <zephyr/dt-bindings/gpio/gpio.h>\n"
    snippet += "/ {\n"
    snippet += "\tleds {\n"
    snippet += '\t\tcompatible = "gpio-leds";\n'

    used_interfaces = set()

    for i, conn in enumerate(leds):
        soc_if, _, node = conn
        name = node.name if node.name else "LED"
        addr = node.get_node_interface_address('gpio')
        if addr == None:
            logging.warning(f"Can't find address for node {node.name}. Skipping node.")
            continue
        label = node.label
        snippet += f"\t\t{label}: led_{i} {{\n"
        snippet += f"\t\t\tgpios = <&{soc_if} {addr} GPIO_ACTIVE_HIGH>;\n"
        snippet += f'\t\t\tlabel = "{name}";\n'
        snippet += "\t\t};\n"
        used_interfaces.add(soc_if)

    snippet += "\t};\n"
    snippet += "};\n"

    for interface in used_interfaces:
        snippet += _enable_iface(interface)

    return snippet


def _create_connection_snippet(name, label, addr, compats, soc_if, sensor_type):
    address = f"@{addr:x}" if addr else ""

    snippet = f"&{soc_if} " + "{\n"
    snippet += '\tstatus = "okay";\n'
    snippet += f"\t{label}: {name}" + address + " {\n"

    if compats:
        snippet += f'\t\tcompatible = {compats};\n'

    if addr:
        snippet += f"\t\treg = <{addr:#x}>;\n"

    if sensor_type:
        snippet += f'\t\tfriendly-name = "{sensor_type}";\n'

    snippet += '\t\tstatus = "okay";\n'
    snippet += "\t};\n"
    snippet += "};\n"
    return snippet


def _prep_thermometers(thermometers):
    snippet = ""
    for (i, (soc_if, node_if, temp)) in enumerate(thermometers):
        name = temp.rdp_name if temp.rdp_name else temp.name
        compats = temp.get_compats()
        addr = temp.get_node_interface_address(node_if)
        label = temp.label

        if not addr:
            logging.warning(f"Can't find address for node {temp.name}. Inserting without address.")

        snippet += _create_connection_snippet(name, label, addr, compats, soc_if, 'thermometer')

    return snippet


def _prep_board_yaml(board_name, configs):
    return {
        "board": {
            "name": board_name,
            "vendor": configs["vendor"],
            "socs": configs["board_socs"]
        }
    }


def prepare_zephyr_board_dir(board_name, soc_name, connections, workspace):
    zephyr_base = Path(env.get_var('ZEPHYR_BASE'))
    socs_dir = workspace / "visual-system-designer-resources/zephyr-data/socs"

    soc_dir = socs_dir / soc_name
    with open(soc_dir / "configs.yaml") as f:
        configs = yaml.safe_load(f)

    board_dir = workspace / "boards" / board_name

    # Remove old directory for board of the same name
    if board_dir.exists():
        shutil.rmtree(board_dir)

    os.makedirs(board_dir)

    # XXX: This is the place to implement adding things to devicetree and configs
    #      after reading configuration from the graph. Although, the application
    #      specific configuration should not be added here but to the app config
    #      and overlay.

    with open(board_dir / f"Kconfig.{board_name}", "w") as f:
        f.write(_prep_kconfig_board(board_name, configs))

    with open(board_dir / "board.yml", "w") as f:
        yaml.dump(_prep_board_yaml(board_name, configs), f, indent=2)

    with open(board_dir / f"{board_name}_defconfig", "w") as f:
        f.write(_prep_defconfig(configs, zephyr_base))

    shutil.copyfile(soc_dir / f"{soc_name}.dts", board_dir / f"{board_name}.dts")
    if (soc_dir / 'overlay.dts').exists():
        with open(board_dir / f"{board_name}.dts", "a") as output:
            output.write("\n\n// overlay\n\n")
            with open(soc_dir / 'overlay.dts') as input:
                shutil.copyfileobj(input, output)

            leds, connections = _filter_nodes(
                connections,
                lambda node: node.category.startswith("IO/LED")
            )

            thermometers, connections = _filter_nodes(
                connections,
                lambda node: node.rdp_name in ['ti_tmp108', 'silabs_si7210']
            )

            if len(connections) > 0:
                logging.warning(f"There are {len(connections)} connections that are currently not supported!")
                for soc_if, node_if, component in connections:
                    logging.warning(f" - {component.name}: {node_if} -> {soc_if}")

            output.write("\n\n// nodes from graph\n\n")

            output.write(_prep_leds(leds))
            output.write(_prep_thermometers(thermometers))

    if "additional_files" in configs:
        for file in configs["additional_files"]:
            if (zephyr_base / file).exists():
                shutil.copy2(zephyr_base / file, board_dir)

    return board_dir


def _copy_build_images(board_name, build_dir, dst_dir):
    # Remove builds directory to discard old build artifacts
    if dst_dir.exists():
        shutil.rmtree(dst_dir)

    os.makedirs(dst_dir)
    copy_files = [
        (build_dir / "zephyr/zephyr.dts", dst_dir / "zephyr/zephyr.dts"),
        (build_dir / "zephyr/zephyr.elf", dst_dir / "zephyr/zephyr.elf"),
        (build_dir / "zephyr/.config", dst_dir / "zephyr/.config"),
        (build_dir / "build.log", dst_dir / "build.log"),
    ]
    for src, dest in copy_files:
        if src.exists():
            os.makedirs(dest.parent, exist_ok=True)
            shutil.copy(src, dest)


def compose_west_command(board_name, app_path, build_dir, boards_dir):
    cmd = "west build -p"
    cmd += f" -b {board_name}"
    cmd += f" --build-dir {build_dir}"
    cmd += f" {app_path}"
    cmd += " --"
    cmd += f" -DBOARD_ROOT={boards_dir.absolute()}"
    return cmd


@env.setup_env
def prepare_zephyr_board(graph_file: Path):
    workspace = Path(env.get_workspace())
    with open(graph_file) as f:
        graph_json = json.load(f)

    specification = Specification(workspace / "visual-system-designer-resources/components-specification.json")
    graph = Graph(graph_json, specification)

    try:
        soc, connections = graph.get_soc_with_connections()
    except KeyError as e:
        logging.error(str(e))
        sys.exit(1)

    soc_name = soc.rdp_name

    board_name = re.sub(r'[\s\-+]', '_', graph.name)
    logging.info(f"Creating zephyr board named '{board_name}'")

    board_dir = prepare_zephyr_board_dir(board_name, soc_name, connections, workspace)
    if not board_dir:
        sys.exit(1)
    logging.info(f"Created board configuration in {board_dir}")


def build_zephyr(board_name: str,
                 app_path: Path = Path("demo/blinky-temperature"),
                 quiet: bool = False):
    async def aprint(msg):
        print(msg, end='')

    return asyncio.run(
        build_zephyr_async(
            board_name,
            aprint if not quiet else None,
            None,
            app_path
        )
    )


@env.setup_env
async def build_zephyr_async(board_name: str,
                             print_callback,
                             kill_event,
                             app_path: Path = Path("demo/blinky-temperature")):
    workspace = Path(env.get_workspace())
    build_dir = workspace / 'build'

    # Remove build directory to discard old build files
    if build_dir.exists():
        shutil.rmtree(build_dir)

    os.makedirs(build_dir)
    command = compose_west_command(board_name, app_path, build_dir, workspace)

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    out = bytearray()

    # XXX: There is no .poll() method in asyncio.subprocess so we have to do it manually.
    async def is_running(p):
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(p.wait(), 1e-6)
        return p.returncode is None

    while await is_running(proc):
        if kill_event and kill_event.is_set():
            proc.terminate()
            logging.warning("Aborting Zephyr build")
            break

        line = await proc.stdout.readline()
        out.extend(line)
        if print_callback:
            await print_callback(line.decode())

    await proc.wait()

    output_dir = workspace / 'builds' / board_name
    _copy_build_images(board_name, build_dir, output_dir)

    with open(output_dir / "build.log", "wb") as f:
        f.write(out)

    logging.info(f"Build files saved in {output_dir}")
    return proc.returncode, output_dir
