# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import asyncio
import atexit
import functools
import json
import logging
import os
import re
import signal
import sys

from datetime import datetime
from importlib.resources import files
from multiprocessing import Process
from pathlib import Path
from time import sleep
from typing import Dict

from pipeline_manager_backend_communication.communication_backend import CommunicationBackend
from pipeline_manager_backend_communication.misc_structures import MessageType
from pipeline_manager.scripts.run import script_run as pm_main

from vsd import build
from vsd import env
from vsd import simulate
from vsd.specification import Specification
from vsd.graph import Graph


class RPCMethods:
    def __init__(self, vsd_client: VSDClient):
        self.vsd_client = vsd_client

    def specification_get(self) -> Dict:
        return self.vsd_client.handle_specification_get()

    def app_capabilities_get(self) -> Dict:
        return {
            "stoppable_methods": ["dataflow_run", "custom_build"],
        }

    async def custom_build(self, dataflow: Dict) -> Dict:
        await self.vsd_client.send_progress("custom_build", -1)
        return await self.vsd_client.handle_build(dataflow)

    def dataflow_import(self, external_application_dataflow: Dict) -> Dict:
        # XXX: Just copy the imported dataflow, because it uses the same format
        #      as expected by the frontend.
        return self.vsd_client._ok(external_application_dataflow)

    def dataflow_export(self, dataflow: Dict) -> Dict:
        return self.vsd_client.save_graph(dataflow)

    async def dataflow_run(self, dataflow: Dict) -> Dict:
        await self.vsd_client.send_progress("dataflow_run", -1)
        return await self.vsd_client.handle_run(dataflow)

    def dataflow_stop(self, method: str) -> Dict:
        match method:
            case "dataflow_run":
                self.vsd_client.stop_simulation_event.set()
            case "custom_build":
                self.vsd_client.stop_build_event.set()
            case _:
                logging.warning(f"Unrecognized method: {method}")
        return self.vsd_client._ok("Stopped.")

    def nodes_on_change(self, graph_id, nodes):
        self.vsd_client.last_graph_change = datetime.now()
        logging.debug(f"Last change: {self.vsd_client.last_graph_change}")

    def properties_on_change(self,graph_id, node_id, properties):
        def is_ignored(prop):
            id = (graph_id, node_id, prop['id'])
            return id in self.vsd_client.ignored_property_changes

        if all(is_ignored(prop) for prop in properties):
            logging.debug(f"Change of {node_id} properties ignored")
            return

        self.vsd_client.last_graph_change = datetime.now()
        logging.debug(f"Last change: {self.vsd_client.last_graph_change}")

    def connections_on_change(self, graph_id, connections):
        self.vsd_client.last_graph_change = datetime.now()
        logging.debug(f"Last change: {self.vsd_client.last_graph_change}")

    def graph_on_change(self, dataflow):
        self.vsd_client.last_graph_change = datetime.now()
        logging.debug(f"Last change: {self.vsd_client.last_graph_change}")

    # XXX: The metadata_on_change and position_on_change events don't have to
    #      be recorded. They aren't triggered by actions that modify the graph.

    def metadata_on_change(self, metadata):
        pass

    def position_on_change(self, graph_id, node_id, position):
        pass


class VSDLogHandler(logging.Handler):
    def __init__(self, vsd_client: VSDClient):
        super().__init__()
        self.formatter = logging.Formatter(fmt='%(levelname)s: %(message)s\n')
        self.vsd_client = vsd_client

    def filter(self, record):
        return record.module != 'dts2repl'

    def emit(self, record):
        if self.vsd_client._client.connected:
            msg = self.formatter.format(record)
            self.vsd_client.terminal_write_sync("backend-logs", msg)


class VSDClient:
    def __init__(self, host, port, workspace, app, templates_dir):
        self.specification = Specification(workspace / "visual-system-designer-resources/components-specification.json")
        self.adjust_specifiaction()
        self.workspace = workspace
        self.app = app
        self.templates = templates_dir
        self.stop_simulation_event = asyncio.Event()
        self.stop_build_event = asyncio.Event()
        self._client = CommunicationBackend(host, port)

        self.ignored_property_changes = []
        self.last_graph_change = datetime.now()

    async def start_listening(self):
        await self._client.initialize_client(RPCMethods(self))
        logging.info("Start listening for messages from pipeline manager")
        logging.getLogger().addHandler(VSDLogHandler(self))
        await self._client.start_json_rpc_client()

    def _error(self, msg):
        return {
            'type': MessageType.ERROR.value,
            'content': msg
        }

    async def _notify(self, typ, title, details=""):
        await self._client.request(
            'notification_send',
            {
                "type": typ,
                "title": title,
                "details": details,
            },
        )

    def terminal_write_sync(self, term_name, msg):
        asyncio.run_coroutine_threadsafe(
            self.terminal_write(term_name, msg),
            self._client.loop
        )

    async def terminal_write(self, term_name, msg):
        request = {
            "name": term_name,
            "message": msg.replace("\n", "\r\n"),
        }
        await self._client.request("terminal_write", request),

    async def send_progress(self, method: str, progress: int):
        await self._client.request(
            "progress_change",
            {
                "method": method,
                "progress": progress,
            },
        )

    def _ok(self, msg):
        return {
            'type': MessageType.OK.value,
            'content': msg
        }

    def adjust_specifiaction(self):
        # Add property for LEDs indicating if they are active
        for node in self.specification.spec_json["nodes"]:
            if "category" not in node:
                continue
            if node["category"] == "IO/LED":
                node["properties"].append(
                    {
                        "default": False,
                        "name": "active",
                        "type": "bool"
                    }
                )

        self.specification.spec_json["metadata"]["notifyWhenChanged"] = True

        # Set custom buttons on navigation bar
        if "navbarItems" not in self.specification.spec_json["metadata"]:
            self.specification.spec_json["metadata"]["navbarItems"] = [
                {
                    "name": "Build",
                    "iconName": "build.svg",
                    "procedureName": "custom_build"
                },
                {
                    "name": "Run simulation",
                    "iconName": "Run",
                    "procedureName": "dataflow_run"
                },
            ]

    def handle_specification_get(self):
        return self._ok(self.specification.spec_json)

    def create_led_callback(self, graph_id, led):
        def led_callback(_, state):
            logging.debug(f"LED {led.label} state changed to {str(state)}")

            node_id = led.id
            if not (graph_id and node_id):
                return
            request = {
                'graph_id': graph_id,
                'node_id': node_id,
                'properties': [{
                    'name': 'active',
                    'new_value': state,
                }],
            }
            logging.debug(f'Request {request}')
            response = asyncio.run_coroutine_threadsafe(
                self._client.request('properties_change', request),
                self._client.loop
            )
            logging.debug(f'Response {response}')

        return led_callback

    def create_terminal_callback(self, term_name):
        decoder = simulate.UTF8Decoder()

        @decoder.wrap_callback
        def terminal_callback(char):
            self.terminal_write_sync(term_name, char)

        return terminal_callback

    async def _prepare_binaries(self, graph):
        """
        Check if the application binaries are ready. Build the application if
        binaries are outdated or not found.

        Returns tuple of following values or None if failed:
            board_name: str
            binaries: Dict
        """
        board_name = re.sub('\s', '_', graph.name)
        build_dir = self.workspace / 'builds' / board_name

        def up_to_date(path):
            if not path.exists():
                return False
            ts = os.path.getmtime(str(path.absolute()))

            logging.debug(f"Last graph change: {self.last_graph_change}")
            logging.debug(f"File mtime: {datetime.fromtimestamp(ts)}")
            return datetime.fromtimestamp(ts) > self.last_graph_change

        expect_binaries = {
            "repl": build_dir / f"{board_name}.repl",
            "elf": build_dir / "zephyr/zephyr.elf",
            "dts": build_dir / "zephyr/zephyr.dts",
        }

        # If these files are up to date we can use them.
        if all(map(up_to_date, expect_binaries.values())):
            return board_name, expect_binaries

        # If they are outdated, the application must be rebuilt.
        ret = await self._build(graph, self.stop_build_event)
        if not ret:
            return None

        def must_exist(path):
            if path.exists():
                return True
            else:
                logging.error(f"The {path.name} hasn't been built.")
                return False

        if all(map(must_exist, expect_binaries.values())):
            return board_name, expect_binaries

        return None

    async def handle_run(self, graph_json):
        graph = Graph(graph_json, self.specification)

        prepare_ret = await self._prepare_binaries(graph)
        if not prepare_ret:
            return self._error("Simulation failed")

        # Unpack the values returned from _prepare_binaries
        board_name, binaries = prepare_ret

        try:
            emu, machine = simulate.prepare_simulation(board_name, binaries['elf'], binaries['repl'])
        except Exception as e:
            logging.error(f"Simulation can't be prepared using {binaries['repl']} and {binaries['elf']}:\n\t{e}")
            return self._error("Simulation failed.")

        zephyr_console = simulate._find_chosen('zephyr,console', binaries['dts'])

        for uart, uart_name in simulate.get_all_uarts(machine):
            if uart_name == zephyr_console:
                term_name = f"zephyr-console ({uart_name})"
            else:
                term_name = uart_name

            simulate.register_uart_callback(
                uart,
                self.create_terminal_callback(term_name)
            )

        # Register leds callbacks
        try:
            _, connections = graph.get_soc_with_connections()
        except KeyError as e:
            logging.error(str(e))
            return self._error("Simulation failed.")

        try:
            for source, connection, dest in connections:
                if connection == 'gpio':
                    repl_label = re.sub("_", "", dest.label)
                    logging.info(f"Connecting state observer to {dest.label} ({repl_label})")
                    simulate.register_led_callback(
                        machine, source, repl_label,
                        self.create_led_callback(graph.id, dest)
                    )
                    await self._ignore_property(graph.id, dest.id, "active")
        except Exception as e:
            logging.error(str(e))
            emu.clear()
            return self._error("Simulation failed.")

        logging.info(f"Starting simulation on {board_name}.")
        emu.StartAll()

        await self.stop_simulation_event.wait()
        emu.clear()

        self.stop_simulation_event.clear()

        logging.info(f"Simulation on {board_name} ended.")
        return self._ok("Simulation finished.")

    def handle_stop(self):
        self.stop_simulation_event.set()
        return self._ok("Stopping simulation")

    async def handle_build(self, graph_json):
        graph = Graph(graph_json, self.specification)
        build_ret = await self._build(graph, self.stop_build_event)
        if build_ret:
            return self._ok("Build succeeded.")
        else:
            return self._error("Build failed.")

    async def _build(self, graph, stop_event):
        prepare_ret = self._prepare_build(graph)
        if not prepare_ret:
            return False

        # Unpack the values returned from _prepare_build
        board_dir, board_name, command = prepare_ret

        logging.info(f"Zephyr board configuration prepared in: {board_dir}")
        logging.info(f"To build this demo manually use the following command:\n\t{command}")

        async def print_fun(msg):
            await self.terminal_write('backend-logs', msg)

        build_ret, build_dir = await build.build_zephyr_async(
            board_name,
            print_fun,
            stop_event,
            self.app
        )
        stop_event.clear()

        if build_ret != 0:
            logging.error("Failed to build Zephyr.")
            return False

        logging.info(f"Application build files available in {build_dir}")

        ret = simulate.prepare_renode_files(board_name, self.templates)
        if ret != 0:
            logging.error("Failed to create files needed by Renode.")
            return False

        return True

    def _prepare_build(self, graph):
        soc, connections = graph.get_soc_with_connections()

        soc_name = soc.rdp_name
        board_name = re.sub('\s', '_', graph.name)

        board_dir = build.prepare_zephyr_board_dir(board_name, soc_name, connections, self.workspace)
        if not board_dir:
            None

        command = build.compose_west_command(board_name, self.app, "<build-dir>", self.workspace)
        return board_dir, board_name, command

    def save_graph(self, graph_json):
        graph = Graph(graph_json, self.specification)

        dest_file = self.workspace / 'save' / f"{graph.name}.json"
        os.makedirs(dest_file.parent, exist_ok=True)
        with open(dest_file, 'w') as f:
            json.dump(graph_json, f)

        return self._ok(f"Graphs saved in {dest_file}")

    async def _ignore_property(self, graph_id, node_id, prop_name):
        """
        Save the information needed to recognize ignored properties.
        The property is uniquely identified using graph id, node id and
        property id.
        """
        resp = await self._client.request(
            'properties_get',
            { "graph_id": graph_id, "node_id": node_id }
        )
        for prop in resp['result']:
            if prop["name"] == prop_name:
                self.ignored_property_changes.append(
                    (graph_id, node_id, prop["id"])
                )
                logging.debug("Ignoring: {} {}".format(node_id, prop["id"]))
                break


async def shutdown(loop):
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    print(f"Cancelling {len(tasks)} VSDClient tasks")
    await asyncio.gather(*tasks)
    loop.stop()


def start_vsd_backend(host, port, workspace, application, templates):
    """
    Initializes the client and runs its asyncio event loop until it is interrupted.
    Doesn't return, if signal is caught whole process exits.
    """
    client = VSDClient(host, port, workspace, application, templates)

    loop = asyncio.get_event_loop()

    loop.add_signal_handler(
        signal.SIGINT,
        functools.partial(asyncio.create_task, shutdown(loop))
    )
    loop.run_until_complete(client.start_listening())

    # After loop has ended, exit because there is no work to do.
    sys.exit(0)


@env.setup_env
def start_vsd_app(application: Path = Path("demo/blinky-temperature"),
                  templates_dir: Path = files('vsd.templates').joinpath(""),
                  website_host: str = "127.0.0.1",
                  website_port: int = 9000,
                  vsd_backend_host: str = "127.0.0.1",
                  vsd_backend_port: int = 5000,
                  remote: bool = False,
                  verbosity: str = "INFO"):

    logging.basicConfig(level=verbosity, format="%(levelname)s:VSD backend:\t%(message)s")

    workspace = Path(env.get_workspace())
    if remote:
        pm_args = (
            "pipeline_manager",  # The first argument must be a program name.
            "--skip-frontend",
            "--backend-host", website_host,
            "--backend-port", str(website_port),
            "--tcp-server-host", vsd_backend_host,
            "--tcp-server-port", str(vsd_backend_port),
            "--verbosity", "INFO",
        )
    else:
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
