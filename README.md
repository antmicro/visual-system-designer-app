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
  --templates-dir PATH        [default: vsd/templates]
  --website-host TEXT         [default: 127.0.0.1]
  --website-port INTEGER      [default: 9000]
  --vsd-backend-host TEXT     [default: 127.0.0.1]
  --vsd-backend-port INTEGER  [default: 5000]
  --verbosity TEXT            [default: INFO]
```

## Using the VSD application

After the VSD application is launched it can be used to design graphs.
Graphs can either be designed from scratch or from another graph imported using the "Load graph file" option.

Visual System Designer is also capable of running a Zephyr demo application based on the created graphs.

To build Zephyr on the current graph use the "Build" button.
After the build has succeeded, simulation may be run using the "Run simulation" button.
The build logs and Zephyr console output are available in dedicated terminals on the bottom of the screen.

## Using VSD from command line

VSD can be also used as a command line utility to execute each step of the application build process separately, without the need to start the VSD server.
These commands can be used when you have obtained a graph from another source (e.g. from [designer.antmicro.com](https://designer.antmicro.com) or using `vsd run` command).

Available commands:

- `prepare-zephyr-board` -- prepare Zephyr board configuration based on given graph
- `build-zephyr` -- build Zephyr for board of given name (previously prepared from graph)
- `prepare-renode-files` -- prepare Renode files needed to run simulation using build results
- `simulate` -- start simulation of prepared application

To get more information about arguments and options for each command run it with `--help` option.

## Example application

The VSD app comes with its own Zephyr demo ([demo/blinky-temperature](./demo/blinky-temperature/)) which can be used on a predefined graph ([stm32-led-thermometer.json](./demo/stm32-led-thermometer.json)).
To run that demo interactively you can start the VSD app, import the graph and run the application using "Run" button.

To prepare and run the demo in the shell execute following commands:

```
vsd prepare-zephyr-board demo/stm32-led-thermometer.json
vsd build-zephyr demo-blinky-temp --app-path demo/blinky-temperature
vsd prepare-renode-files demo-blinky-temp
vsd simulate demo-blinky-temp
```

## Demo with pipeline manager hosted on the internet


### Building and hosting Pipeline Manager

In order to build Pipeline Manager application you have to download its repo from GitHub and additionally install `pipeline-manager-backend-communication`.
After that the application is built using `build` script from Piepline Manager repo.

```sh
git clone git+https://github.com/antmicro/kenning-pipeline-manager.git
pip install ./kenning-pipeline-manager

pip install git+https://github.com/antmicro/kenning-pipeline-manager-backend-communication.git

cd kenning-pipeline-manager
./build server-app --communication-server-host localhost --communication-server-port 9000 --output-directory website
```

The `website` directory can now be served using any http server (e.g. the one included in Python3 distribution):

```sh
python3 -m http.server -d kenning-pipeline-manager/website
```

### Running the demo

1. Start VSD app
    ```sh
    vsd run --application visual-system-designer-app/demo/blinky-temperature
    ```
2. Go to http://localhost:8000.
3. Use VSD as usual (e.g. load `visual-system-designer-app/demo/stm32-led-thermometer.json` and click "Run").

## License

This project is published under the [Apache-2.0](LICENSE) license.
