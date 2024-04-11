# Visual System Designer

Copyright (c) 2023 [Antmicro](https://www.antmicro.com)

The Visual System Designer app is a local multi-tool which incorporates the diagramming capabilities of the online [Visual System Designer](https://designer.antmicro.com/) which can be used for building block design of embedded systems in a diagramming workflow.
For more background on Visual System Designer and its goals, please read the [introductory blog note on Antmicro's blog](https://antmicro.com/blog/2023/09/build-embedded-systems-with-vsd/).

The tool can also be used to generate and build [Zephyr RTOS](https://zephyrproject.org/)-based firmware and simulate it using [Renode](https://www.renode.io), Antmicro's open source simulation framework, visualizing the state of the simulation.

## Demo

https://github.com/antmicro/visual-system-designer-app/assets/114056459/9262c9db-82ad-4abf-ac39-a331427065c2

## Prerequisites

The VSD application currently depends on other projects: kenning-pipeline-manager, Zephyr and Renode, therefore their dependencies must be installed first.
Make sure that you have installed all the programs mentioned below.
Any other dependencies (e.g. Python requirements or Zephyr workspace) will be downloaded later by the setup script.

(the following package names are for Debian based systems)

* [Pipeline Manager dependencies](https://github.com/antmicro/kenning-pipeline-manager#prerequisites)

  ```
  npm python3 python3-pip
  ```
* [Zephyr dependencies](https://docs.zephyrproject.org/latest/develop/getting_started/index.html#install-dependencies)

  ```
  git cmake ninja-build gperf ccache dfu-util device-tree-compiler wget python3-dev python3-pip python3-setuptools \
  python3-tk python3-wheel xz-utils file make gcc gcc-multilib g++-multilib libsdl2-dev libmagic1
  ```
* [Renode dependencies](https://github.com/renode/renode#installing-dependencies)

  ```
  mono-complete
  ```

NOTE: On Arch based systems additionally the `gtk-sharp` package must be installed to successfully run Renode.

## Setup

To prepare project's environment and download necessary files, run:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vsd init workspace
export VSD_WORKSPACE=$(pwd)/workspace
```

## Starting the VSD application

The most convenient way to run VSD is to use it interactively:

```
vsd run
```

After running this command the VSD server will start and the application can be used in a web browser (by default at http://localhost:9000).
It can be used to design a graph of the platform, build an example Zephyr application on designed platform and run it in simulation using Renode.

To adjust the options used to start the VSD application use the following options (those can be listed with `--help`):

```
Usage: vsd run [OPTIONS]

Options:
  --application PATH          [default: demo/blinky-temperature]
  --website-host TEXT         [default: 127.0.0.1]
  --website-port INTEGER      [default: 9000]
  --vsd-backend-host TEXT     [default: 127.0.0.1]
  --vsd-backend-port INTEGER  [default: 5000]
  --remote / --no-remote      [default: no-remote]
  --spec-mod PATH
  --verbosity TEXT            [default: INFO]
```

## Using the VSD application

After the VSD application is launched it can be used to design graphs.
Graphs can either be designed from scratch or from another graph imported using the "Load graph file" option.

Visual System Designer is also capable of running a Zephyr demo application based on the created graphs.

To build Zephyr on the current graph use the "Build" button.
After the build has succeeded, simulation may be run using the "Run simulation" button.
The build logs and Zephyr console output are available in dedicated terminals on the bottom of the screen.

### Modifying specification

If you want to add some new nodes to the specification or modify existing ones you have to define a JSON file with such modifications.
An example file (with modifications needed while running VSD interactively) is present in [vsd/spec_mods/interactive.json](./vsd/spec_mods/interactive.json).
After defining such files you must specify their paths while starting VSD app (they will be applied in the order they were specified):

```
vsd run --spec-mod mod1.json --spec-mod mod2.json
# or
vsd prepare-zephyr-board board-graph.json --spec-mod mod1.json --spec-mod mod2.json
```

To modify specification without running VSD app you may use [tools/modify_specification.py](./tools/modify_specification.py) script.

#### Specification modifications file format

On the high level, the JSON file, which contains the description of modifications, has three keys:

* `"metadata"` -- each field specified here will replace the one in metadata of original specification
* `"add_nodes"` -- new nodes will be directly added to the original specification
* `"mods"` -- each entry in this section describes how to modify a group of nodes specified in `"names"` list:
  - `"add_property"` -- properties specified here will be added to all specified nodes
  - `"add_interface"` -- interfaces specified here will be added to all specified nodes

Example file:
```JSON
{
    "metadata": {
        "notifyWhenChanged": true
    },
    "add_nodes": [
        {
            "abstract": false,
            "category": "Category/SomeNode",
            "name": "SomeNode",
            "properties": [
                {
                    "default": "",
                    "name": "property1",
                    "type": "text"
                }
            ],
            "interfaces": [
                {
                    "direction": "inout",
                    "maxConnectionsCount": -1,
                    "name": "interface1",
                    "side": "left",
                    "type": "interface1"
                }
            ]
        }
    ],
    "mods": [
        {
            "names": ["LED"],
            "add_properties": [
                    {
                        "default": false,
                        "name": "active",
                        "type": "bool"
                    }
            ]
        },
        {
            "names": [
                "bme280",
                "sht4xd",
                "tmp108",
                "si7210"
            ],
            "add_properties": [
                {
                    "default": 20.0,
                    "name": "temperature",
                    "type": "number"
                }
            ]
        }
    ]
}
```

## Using VSD from command line

VSD can also be used as a command line utility to prepare and simulate a demo on graph created with VSD.
There are two available commands: `prepare-zephyr-app` and `simulate`.
These commands process graph obtained earlier (e.g. from [designer.antmicro.com](https://designer.antmicro.com) or using `vsd run` command).

### `prepare-zephyr-app` command

This command is used to prepare and build Zephyr application for given board graph.

```
usage: vsd prepare-zephyr-app graph_file source_dir [--from-template template_dir] [--force]
```

It requires providing:

* `graph_file` - file defining the VSD graph representing the design
* `source_dir` - a directory where the Zephyr project is placed (or where the generated project from template should be placed)

There are two possible options to provide application sources for this command:

- `--from-template` - specify the directory which contains a template for the project
- `--force` - specify the application template (by name or directory), which will be used to generate the application sources. Currently there is only one template available to use specifying its name: `blinky-temperature`.

#### Example

Few basic usage examples:

- Building demo from sources:
  ```
  vsd prepare-zephyr-app demo/stm32-led-thermometer.json demo/blinky-temperature
  ```
- Building demo from template:
  ```
  vsd prepare-zephyr-app demo/stm32-led-thermometer.json ./my-project --from-template demo/templates/blinky-temperature/
  ```

### `simulate` command

This command is used to start Renode simulation of the demo build in the previous step.
The `board_name`, which has to be specified as an argument, is obtained from the graph name by substituting all white and special characters with underscore.
The board name is also printed in the previous step.

```
usage: vsd simulate board_name
```

#### Example

Firstly, building demo, e.g. from template as demonstrated in `prepare-zephyr-app`:

```
vsd prepare-zephyr-app demo/stm32-led-thermometer.json ./my-blinky --from-template demo/templates/blinky-temperature/
```

Secondly, run `vsd simulate` with board name, here:

```
vsd simulate demo_blinky_temp
```

## Example application

The VSD app comes with its own Zephyr demo ([demo/blinky-temperature](./demo/blinky-temperature/)) which can be used on a predefined graph ([stm32-led-thermometer.json](./demo/stm32-led-thermometer.json)).
To run that demo interactively you can start the VSD app, import the graph and run the application using "Run" button.

To prepare and run the demo in the shell execute following commands:

```
vsd prepare-zephyr-app demo/stm32-led-thermometer.json demo/blinky-temperature
vsd simulate demo_blinky_temp
```

## Demo with frontend hosted on a remote server

### Building and hosting Pipeline Manager

In order to build Pipeline Manager frontend, create the `venv` environment and install [Pipeline Manager](https://github.com/antmicro/kenning-pipeline-manager):

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install git+https://github.com/antmicro/kenning-pipeline-manager.git
```

The frontend requires additional assets (icons, graphics, ...) to render properly - they can be obtained from [VSD resources repository](https://github.com/antmicro/visual-system-designer-resources):

```sh
git clone https://github.com/antmicro/visual-system-designer-resources.git
```

After obtaining all requirements, the frontend can be built with:

```sh
pipeline_manager build server-app --communication-server-host localhost --communication-server-port 9000 --output-directory website --workspace-directory pm-workspace --assets-directory visual-system-designer-resources/assets/
```

The `--communication-server-host` and `--communication-server-port` specify the address from which the `vsd run` command will connect (from the user desktop perspective, hence `localhost` is sufficient).

The `website` directory can now be served using any HTTP server (e.g. the one included in Python3 distribution):

```sh
python3 -m http.server -d ./website
```

### Running the demo

Assuming the commands are executed in the root directory for this project:

1. Prepare the workspace as described in [Setup](#setup).
1. Start VSD app (the `--application <dir>` is the path to the sources for the Zephyr application)
    ```sh
    vsd run --app demo/blinky-temperature
    ```
2. Go to address hosting Pipeline Manager (using above Python server go to http://localhost:8000).
3. Use VSD as usual (e.g. load [`visual-system-designer-app/demo/stm32-led-thermometer.json`](demo/stm32-led-thermometer.json) and click "Run").

## License

This project is published under the [Apache-2.0](LICENSE) license.
