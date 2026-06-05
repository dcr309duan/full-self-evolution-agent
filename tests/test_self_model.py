import os
import tempfile
import json
import pytest
from self_model.builder import build_graph
from self_model.graph import Graph

@pytest.fixture
def small_test_dir():
    # Create a temporary directory with a minimal project structure
    tmpdir = tempfile.mkdtemp()
    # Create a Python file
    pyfile = os.path.join(tmpdir, "example.py")
    with open(pyfile, "w") as f:
        f.write("import os\n\ndef foo():\n    pass\n")
    # Create a subdirectory with another file
    subdir = os.path.join(tmpdir, "subpkg")
    os.makedirs(subdir)
    subfile = os.path.join(subdir, "bar.py")
    with open(subfile, "w") as f:
        f.write("from example import foo\n\ndef baz():\n    foo()\n")
    # Create a non-Python file (should be ignored)
    txtfile = os.path.join(tmpdir, "readme.txt")
    with open(txtfile, "w") as f:
        f.write("Just a text file.")
    return tmpdir

def test_builder_creates_graph(small_test_dir):
    graph = build_graph(small_test_dir)
    assert isinstance(graph, Graph), "build_graph should return a Graph instance"
    assert len(graph.nodes) > 0, "Graph should contain nodes"

def test_graph_contains_expected_nodes(small_test_dir):
    graph = build_graph(small_test_dir)
    # Expect nodes for modules: example, subpkg.bar, and possibly the root
    node_names = [node.name for node in graph.nodes]
    assert "example" in node_names, "Graph should have node for example module"
    assert "subpkg.bar" in node_names, "Graph should have node for subpkg.bar module"
    # The root directory itself might be a node; check if present
    # root_name = os.path.basename(small_test_dir)
    # assert root_name in node_names, "Graph should have node for root directory"

def test_graph_contains_expected_edges(small_test_dir):
    graph = build_graph(small_test_dir)
    # Expect edge from subpkg.bar to example (import)
    edge_found = False
    for edge in graph.edges:
        if edge.source == "subpkg.bar" and edge.target == "example":
            edge_found = True
            break
    assert edge_found, "Graph should have edge from subpkg.bar to example"
    # Also expect edge from example to os (import)
    edge_os = False
    for edge in graph.edges:
        if edge.source == "example" and edge.target == "os":
            edge_os = True
            break
    assert edge_os, "Graph should have edge from example to os"

def test_query_methods(small_test_dir):
    graph = build_graph(small_test_dir)
    # Test query by name
    example_node = graph.get_node("example")
    assert example_node is not None, "get_node should return node for example"
    assert example_node.name == "example"
    # Test query by type (assuming nodes have a 'type' attribute)
    module_nodes = graph.get_nodes_by_type("module")
    assert len(module_nodes) >= 2, "Should find at least two module nodes"
    # Test query for edges from a specific node
    edges_from_example = graph.get_edges_from("example")
    assert len(edges_from_example) > 0, "example should have outgoing edges"
    # Test query for edges to a specific node
    edges_to_example = graph.get_edges_to("example")
    assert len(edges_to_example) > 0, "example should have incoming edges"

def test_json_serialization_round_trip(small_test_dir):
    graph = build_graph(small_test_dir)
    # Serialize to JSON
    json_str = graph.to_json()
    # Deserialize back
    graph2 = Graph.from_json(json_str)
    # Compare nodes (order may differ)
    assert len(graph.nodes) == len(graph2.nodes), "Node count should match"
    for node in graph.nodes:
        # Find matching node by name
        match = [n for n in graph2.nodes if n.name == node.name]
        assert len(match) == 1, f"Node {node.name} should exist in deserialized graph"
        # Compare attributes (assuming node has __dict__ or similar)
        # For simplicity, compare as dicts if available
        if hasattr(node, 'to_dict'):
            assert node.to_dict() == match[0].to_dict()
        else:
            # Fallback: compare name and type
            assert node.type == match[0].type
    # Compare edges
    assert len(graph.edges) == len(graph2.edges), "Edge count should match"
    for edge in graph.edges:
        match = [e for e in graph2.edges if e.source == edge.source and e.target == edge.target and e.label == edge.label]
        assert len(match) == 1, f"Edge {edge.source}->{edge.target} should exist in deserialized graph"
    # Also test that JSON is valid
    parsed = json.loads(json_str)
    assert "nodes" in parsed, "JSON should contain 'nodes' key"
    assert "edges" in parsed, "JSON should contain 'edges' key"