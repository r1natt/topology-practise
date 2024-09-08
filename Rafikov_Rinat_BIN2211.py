import re
from typing import List, TypedDict, Set, Dict, Tuple
from pprint import pprint 
import glob
import sys
import graphviz as gv


PROCESSING_DIR = "./out"
OUT_GRAPH_FILENAME = "./img/rafikov_topology"
"""
PROCESSING_DIR - папка с файлами как в примере
OUT_GRAPH_FILENAME - название файла с топологией
"""


class Node(TypedDict):
    node: str
    port_id: str

class Edge(TypedDict):
    source_node: Node
    target_node: Node

class Connections:
    def __init__(self):
        self.expanded_edges: List[Edge] = []
        self.edges: List[Set] = []

    def _is_edge_in_list(self, obj: Edge):
        obj_node1 = obj["source_node"]["node"]
        obj_node2 = obj["target_node"]["node"]
        obj_edge_set = set([obj_node1, obj_node2])
        if obj_edge_set in self.edges:
            return True
        return False

    def append_edge(self, obj: Edge):
        if not self._is_edge_in_list(obj):
            self.expanded_edges.append(obj)
            
            node1 = obj["source_node"]["node"]
            node2 = obj["target_node"]["node"]
            self.edges.append(set([node1, node2]))


class TopologyDict(dict):
    def __init__(self, expanded_edges: List[Edge]):
        self.edges = expanded_edges
        self.transform()

    def transform(self):
        for edge in self.edges:
            node1_name = edge["source_node"]["node"]
            node1_port = edge["source_node"]["port_id"]
            node2_name = edge["target_node"]["node"]
            node2_port = edge["target_node"]["port_id"]

            node1 = (node1_name, node1_port)
            node2 = (node2_name, node2_port)
            self[node1] = node2


class Processing:
    def __init__(self):
        self.dir = PROCESSING_DIR
        self.connections = Connections()

        self.processing_files()

    def processing_files(self):
        files = glob.glob(self.dir + "/*")
        for file_path in files:
            self.unparse_one_file(file_path)

    def unparse_devices_list_of_lines(self, lines: List):
        unparsed_devices = []
        for line in lines:
            del_extra_spaces = re.sub(r'\s\s+', ';', line)
            # Строкой выше я превращаю "SW1              Eth 0/0" в "SW1;Eth 0/0"
            # Использую регулярное выражение от 2х пробелов и более, а не от 
            # одного, тк есть данные "Eth 0/0", которые бы разделились так 
            # ["Eth", "0/0"]
            unparsed_devices.append(del_extra_spaces.split(";"))

        for device in unparsed_devices:
            """
            Костыльное решение, но все же
            В прошлом пункте может быть такая ситуация, что значения platform и 
            port_id стоят очень близко (расстояние между ними 1 пробел)
            В коде ниже я обрабатываю этот случай

            Важно, что мой код корректно работает, только если Port ID состоит 
            из двух частей "Eth" и "0/2". В ином случае ошибка обрабатываться 
            не будет
            """
            if device[-1].count(' ') >= 2:
                platform_n_port = device[-1].split(" ")
                port = " ".join(platform_n_port[-2:])
                platform = " ".join(platform_n_port[:-2])
                
                device.pop(-1)
                device.insert(len(device), platform)
                device.insert(len(device), port)

        return unparsed_devices

    def get_text_from_file(self, file_path):
        with open(file_path, 'r') as file:
            data = file.read()
            return data

    def unparse_one_file(self, file_path):
        """
        В этой функции я обрабатываю текст файла который подается на вход
        Из файла мне нужно извлечь:
            Узел, который рассматривается в данном файле
            И Узлы, которые соединены с первым

        Во втором условии я определяю source_node из строки "R2>show cdp neighbors"
        В третьем условии я определяю является ли рассматриваемая строка 
            строкой в которой определяются названия колонок Device ID , 
            Local Intrfce, Holdtme, Capability, Platform, Port ID
            Так как я все еще перебираю строки в цикле, это значит, что 
            следующие строки будут содержать в себе эти самые узлы. Я отмечаю 
            в переменной is_device_id_passed что строка с названиями колонок 
            пройдена
        В первом условии (так как строка с названиями колонок пройдена), я 
            сохраняю данные в список
        """

        file_text = self.get_text_from_file(file_path)
        data = file_text.split("\n")

        source_node_name = "-1"
        target_nodes = []
        is_device_id_passed = False

        for n, i in enumerate(data):
            if is_device_id_passed:
                if i != "":
                    target_nodes.append(i)
            if ">" in i:
                source_node_name = i.split(">")[0]
                # Я буквально разделяю строку по символу ">", получаю список
                # ["R2", "show cdp neighbors"] и беру первый элемент
            elif "Device ID" in i:
                is_device_id_passed = True

        unparsed_devices = self.unparse_devices_list_of_lines(target_nodes)

        for device in unparsed_devices:
            source_node = Node(node=source_node_name, port_id=device[1])
            target_node = Node(node=device[0], port_id=device[-1])

            pair = Edge(source_node=source_node, target_node=target_node)
            self.connections.append_edge(pair)
        return (source_node, unparsed_devices)


class Graph:
    def __init__(self, connections, filename="./topology"):
        self.connections = connections
        self.filename = filename
        self.graph = gv.Graph(format="svg")
        self.styles = {
            "graph": {
                "label": "Network Map",
                "fontsize": "16",
                "fontcolor": "white",
                "bgcolor": "#3F3F3F",
                "rankdir": "BT",
            },
            "nodes": {
                "fontname": "Helvetica",
                "shape": "box",
                "fontcolor": "white",
                "color": "#006699",
                "style": "filled",
                "fillcolor": "#006699",
                "margin": "0.4",
            },
            "edges": {
                "style": "dashed",
                "color": "green",
                "arrowhead": "open",
                "fontname": "Courier",
                "fontsize": "14",
                "fontcolor": "white",
            },
        }
        self.draw_topology()

    def apply_styles(self):
        self.graph.graph_attr.update(
                ("graph" in self.styles and self.styles["graph"]) or {}
            )
        self.graph.node_attr.update(
                ("nodes" in self.styles and self.styles["nodes"]) or {}
            )
        self.graph.edge_attr.update(
                ("edges" in self.styles and self.styles["edges"]) or {}
            )

    def draw_topology(self):
        topology_dict: Dict[Tuple, Tuple] = TopologyDict(self.connections.expanded_edges)
        print("topology_dict:")
        pprint(topology_dict)

        nodes = set(
            [item[0] for item in list(topology_dict.keys()) + list(topology_dict.values())]
        )

        for node in nodes:
            self.graph.node(node)

        for key, value in topology_dict.items():
            head, t_label = key
            tail, h_label = value
            self.graph.edge(head, tail, headlabel=h_label, taillabel=t_label, label=" " * 12)

        self.apply_styles()
        filename = self.graph.render(filename=self.filename)
        print("Topology saved in", filename)


if __name__ == "__main__":
    p = Processing()
    connections = p.connections
    g = Graph(connections, filename=OUT_GRAPH_FILENAME)
