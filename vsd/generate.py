import logging
import os
import shutil

from vsd.utils import filter_nodes
from jinja2 import Environment, FileSystemLoader, select_autoescape


supported_sensors = {
    'bosch_bme280': 'thermometer',
    'sensirion_sht4x': 'thermometer',
    'silabs_si7210': 'thermometer',
    'ti_tmp108': 'thermometer',
}


def generate_app(app_template_path, board_name, connections, workspace, output_dir=None):
    template_env = Environment(
        autoescape=select_autoescape(),
        line_statement_prefix="//!",
        line_comment_prefix="///",
        loader=FileSystemLoader(app_template_path),
    )

    # Parse graph and get nodes that will be generated
    leds, connections = filter_nodes(
        connections,
        lambda if_name, if_type, node: node.category.startswith("IO/LED")
    )
    thermometers, connections = filter_nodes(
        connections,
        lambda if_name, if_type, node: node.rdp_name in supported_sensors and supported_sensors[node.rdp_name] == "thermometer"
    )

    app_name = app_template_path.name
    generated_dir = output_dir or (workspace / "generated" / f"{board_name}_{app_name}")
    logging.info(f"Generating app sources in {generated_dir}")

    if generated_dir.exists():
        logging.info(f"The {generated_dir} directory will be cleaned before generating the application code in it.")
        shutil.rmtree(generated_dir)

    os.makedirs(generated_dir)

    context = {
        "all_labels": list(map(lambda x: x[2].label, leds)) + list(map(lambda x: x[2].label, thermometers)),
        "leds": list(map(lambda x: x[2].label, leds)),
        "thermometers": list(map(lambda x: x[2].label, thermometers)),
    }

    for file in app_template_path.glob("**/*"):

        rel_path = file.relative_to(app_template_path)

        if file.is_file():
            template = template_env.get_template(str(rel_path))
            with open(generated_dir / rel_path, "w+") as f:
                f.write(template.render(context))
        elif file.is_dir():
            os.makedirs(generated_dir / rel_path)

    # Return generated_dir because it is also created when output_dir argument isn't specified.
    return generated_dir
