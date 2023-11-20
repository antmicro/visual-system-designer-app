# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import json
import logging


class Specification():
    def __init__(self, spec_path):
        self._parse_specification(spec_path)

    def _parse_specification(self, spec_path):
        """Return specification in format that is easier to operate on."""
        with open(spec_path) as f:
            self.spec_json = json.load(f)

        metadata = self.spec_json['metadata']

        nodes = {}
        categories = {}
        abstract = {}

        for node in self.spec_json['nodes']:
            if 'isCategory' in node and node['isCategory']:
                categories[node['category'].split("/")[-1]] = node
                continue
            if 'abstract' in node and node['abstract']:
                abstract[node['name']] = node
                continue
            nodes[node['name']] = node

        self.metadata = metadata
        self.nodes = nodes
        self.categories = categories
        self.abstract = abstract

    def get_node_spec(self, node_name):
        if node_name in self.nodes:
            logging.debug(f"{node_name} is a node.")
            node = self.nodes[node_name]
        elif node_name in self.categories:
            logging.debug(f"{node_name} is a category.")
            node = self.categories[node_name]
        elif node_name in self.abstract:
            logging.debug(f"{node_name} is an abstract node.")
            return None
        else:
            logging.warning(f"Node {node_name} not found.")
            return None

        # XXX: maybe resolve on more levels?
        if 'extends' in node:
            for ext_name in node['extends']:
                if ext_name in self.abstract:
                    node = {**node, **self.abstract[ext_name]}
                elif ext_name in self.categories:
                    node = {**node, **self.categories[ext_name]}
                else:
                    logging.warning(f"Not found the extend node: {ext_name}")
        return node

    def get_socs(self):
        soc_names = []
        for name, node in self.categories.items():
            if node['category'].startswith("SoC"):
                soc_names.append(name)
        return soc_names
