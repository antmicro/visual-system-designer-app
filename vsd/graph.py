# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import logging
import re


class Node():
    def __init__(self, node, specification):
        self._node = node
        self._spec = specification.get_node_spec(node['name'])
        self._label = None
        self.id = node['id']
        self.connections = {}
        self.interfaces = {}

        if 'interfaces' not in node:
            return

        for interface in node['interfaces']:
            self.interfaces[interface['id']] = interface['name']
            self.connections[interface['id']] = []

    def __repr__(self):
        if 'urls' in self._spec and 'rdp' in self._spec['urls']:
            rdp = self._spec['urls']['rdp']
        else:
            rdp = ''
        return f"<Node '{self._node['name']}' {rdp}>"

    def is_soc(self):
        return 'SoC' in self._spec['category']

    @property
    def rdp_name(self):
        if 'urls' in self._spec and 'rdp' in self._spec['urls']:
            rdp_link = self._spec['urls']['rdp']
        else:
            return None
        return rdp_link.split("/")[-1]

    @property
    def name(self):
        if 'name' not in self._node:
            return None
        return self._node['name']

    @property
    def label(self):
        if self._label:
            return self._label

        id = self.id.split('-')[-1].lower()
        cat =  self._spec['category'].split('/')[-1].lower()

        self._label = f"{cat}_{id}"
        return self._label

    @property
    def category(self):
        if 'category' in self._spec:
            return self._spec['category']
        return 'Other'

    def get_compats(self):
        if 'additionalData' in self._spec and 'compats' in self._spec['additionalData']:
            compats = self._spec['additionalData']['compats']
            return ', '.join(f'"{c}"' for c in compats)
        return None

    def get_node_interface_address(self, interface):
        if 'properties' not in self._node:
            return None

        for prop in self._node['properties']:
            if f'address ({interface})' in prop['name']:
                logging.debug(f"Found address property {prop['name']} in {self.name}: {prop['value']}")
                try:
                    value = int(prop['value'], base=16)
                except ValueError:
                    logging.error(f"Missing or invalid value for {prop['name']}: '{prop['value']}'")
                    return None
                return value

        return None


class Graph():
    def __init__(self, graph_json, specification):
        self.nodes = {}
        self.socs = []
        self.interface_to_node = {}

        for graph_node in graph_json['graph']['nodes']:
            node_id = graph_node['id']
            node = Node(graph_node, specification)
            self.nodes[node_id] = node

            for id in node.interfaces:
                self.interface_to_node[id] = node_id

            if node.is_soc():
                self.socs.append(node_id)

        # Get name form graph or from SoC name
        name = graph_json['graph'].get('name')
        if not name:
            if len(self.socs) > 0:
                name = self.nodes[self.socs[0]].name
            if not name:
                name = "Untitled_graph"

        self.name = re.sub("\s", "_", name)
        self.id = graph_json['graph']['id']

        for edge in graph_json['graph']['connections']:
            id_from = edge['from']
            id_to = edge['to']

            node_from = self.interface_to_node[id_from]
            node_to = self.interface_to_node[id_to]

            self.nodes[node_from].connections[id_from].append(id_to)
            self.nodes[node_to].connections[id_to].append(id_from)

    def get_soc_with_connections(self):
        if len(self.socs) == 0:
            raise KeyError("Haven't found any SoC nodes in the graph")

        soc_id = self.socs[0]
        soc_node = self.nodes[soc_id]

        if len(self.socs) > 1:
            logging.warning(f"Found more than one SoC in the graph. Using {soc_node.name}.")

        connections = []
        for id, neighbors in soc_node.connections.items():
            soc_interface_name = soc_node.interfaces[id]
            for n in neighbors:
                neighbor_node = self.nodes[self.interface_to_node[n]]
                node_interface_name = neighbor_node.interfaces[n]
                connections.append((soc_interface_name, node_interface_name, neighbor_node))
        return soc_node, connections
