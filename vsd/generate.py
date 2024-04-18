import itertools
import logging
import os
import re
import shutil
import yaml

from collections import defaultdict


supported_sensors = {
    'bosch_bme280': 'thermometer',
    'sensirion_sht4x': 'thermometer',
    'silabs_si7210': 'thermometer',
    'ti_tmp108': 'thermometer',
}


def _filter_nodes(connections, filter_fn):
    filtered, other = [], []
    for conn in connections:
        _, _, component = conn
        if filter_fn(component):
            filtered.append(component)
        else:
            other.append(conn)
    return filtered, other


def translate_code_snippet(snippet):
    """
    Snippets which use {% %} syntax are easier to write,
    because we don't have to excape each { and } symbols.
    """
    # Replace { and } with {{ and }} (to not consume then during string formatting)
    snippet = re.sub(r"{(?=[^%])", "{{", snippet)
    snippet = re.sub(r"(?<=[^%])}", "}}", snippet)

    # Replace "{% label %}" with "{label}"
    snippet = re.sub(r"{% *([\w_]+) *%}", r"{\1}", snippet)

    return snippet


def generate_code_snippets(label, snippets_templates, code_snippets):
    # Add snippet with definition of dts node label
    code_snippets['discover'].append(f"#define __{label.upper()}_NODE DT_NODELABEL({label})")

    # Generate snippets read from template dir for given node type
    for name, template in snippets_templates.items():
        code_snippets[name].append(
            template.format(name=f"__{label}", name_caps=f"__{label.upper()}"))


def generate_app(app_template_path, board_name, connections, workspace):
    with open(app_template_path / "nodes.yml") as f:
        nodes_templates = yaml.safe_load(f)

    # Parse graph and get nodes that will be generated
    leds, connections = _filter_nodes(
        connections,
        lambda node: node.category.startswith("IO/LED")
    )
    thermometers, connections = _filter_nodes(
        connections,
        lambda node: node.rdp_name in supported_sensors and supported_sensors[node.rdp_name] == "thermometer"
    )
    nodes = [
        *zip(leds, itertools.repeat("led")), 
        *zip(thermometers, itertools.repeat("thermometer")), 
    ]

    code_snippets = defaultdict(list)

    snippets_templates = nodes_templates["snippet templates"]
    for node_templates in snippets_templates.values():
        for k in node_templates:
            node_templates[k] = translate_code_snippet(node_templates[k])

    # Generate app source in 'workspace/generated' directory
    for node, node_type in nodes:
        label = node.label
        generate_code_snippets(label, snippets_templates[node_type], code_snippets)

    # Create one snippet for each key, by joining individual snippets with new lines
    code_snippets = {
        key: "\n".join(snippets) for key, snippets in code_snippets.items()
    }

    app_name = app_template_path.name
    generated_dir = workspace / "generated" / f"{board_name}_{app_name}"
    logging.info(f"Generating app sources in {generated_dir}")

    if generated_dir.exists():
        shutil.rmtree(generated_dir)

    os.makedirs(generated_dir)

    shutil.copy(app_template_path / "prj.conf", generated_dir / "prj.conf")
    shutil.copy(app_template_path / "CMakeLists.txt", generated_dir / "CMakeLists.txt")
    shutil.copytree(app_template_path / "src", generated_dir / "src")

    with open(app_template_path / "src/main.c") as f:
        main_template = f.read()

    with open(generated_dir / "src/main.c", "w+") as f:
        f.write(main_template.format(**code_snippets))

    return generated_dir
