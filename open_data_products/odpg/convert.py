"""Convert external graph formats into ODPG YAML documents."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

SCHEMA_URL = "https://opendataproducts.org/odpg-v1.0/schema/graph.yaml"
DEFAULT_NODE_TYPE = "Resource"
DEFAULT_EDGE_TYPE = "relatedTo"
DEFAULT_CONFIDENCE = "medium"
SUPPORTED_FORMATS = (
    "jsonld",
    "rdf",
    "graphml",
    "opencypher",
    "gql",
    "gremlin",
    "graphson",
)

FORMAT_ALIASES = {
    "cypher": "opencypher",
    "open-cypher": "opencypher",
    "open_cypher": "opencypher",
    "sparql": "rdf",
    "geosparql": "rdf",
    "ttl": "rdf",
    "turtle": "rdf",
    "nt": "rdf",
    "ntriples": "rdf",
    "n-triples": "rdf",
}


class ODPGBuilder:
    """Collect nodes and edges into an ODPG graph document."""

    def __init__(
        self,
        graph_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        confidence: str = DEFAULT_CONFIDENCE,
    ) -> None:
        self.graph_id = graph_id or "converted-graph"
        self.name = name or "Converted Graph"
        self.description = (
            description or "Graph converted to ODPG from an external graph format."
        )
        self.confidence = confidence or DEFAULT_CONFIDENCE
        self.nodes_by_id: Dict[str, Dict[str, str]] = {}
        self.edges: List[Dict[str, str]] = []
        self.edge_keys: Set[Tuple[str, str, str]] = set()

    def add_node(
        self,
        node_id: Any,
        node_type: Any = None,
        ref: Any = None,
    ) -> str:
        """Add or update one ODPG node and return its normalized id."""
        normalized_id = clean_identifier(node_id)
        if not normalized_id:
            raise ValueError("Cannot add an ODPG node without an id")
        normalized_type = local_name(clean_identifier(node_type)) or DEFAULT_NODE_TYPE
        node_ref = clean_identifier(ref) or "#" + normalized_id

        existing = self.nodes_by_id.get(normalized_id)
        if existing:
            if existing["type"] == DEFAULT_NODE_TYPE and normalized_type:
                existing["type"] = normalized_type
            if existing["$ref"].startswith("#") and not node_ref.startswith("#"):
                existing["$ref"] = node_ref
            return normalized_id

        self.nodes_by_id[normalized_id] = {
            "id": normalized_id,
            "type": normalized_type,
            "$ref": node_ref,
        }
        return normalized_id

    def add_edge(
        self,
        source: Any,
        target: Any,
        edge_type: Any = None,
        confidence: Optional[str] = None,
    ) -> None:
        """Add one ODPG edge, deduplicating by source, target, and type."""
        source_id = self.add_node(source)
        target_id = self.add_node(target)
        normalized_type = local_name(clean_identifier(edge_type)) or DEFAULT_EDGE_TYPE
        key = (source_id, target_id, normalized_type)
        if key in self.edge_keys:
            return
        self.edge_keys.add(key)
        self.edges.append(
            {
                "from": source_id,
                "to": target_id,
                "type": normalized_type,
                "confidence": confidence or self.confidence,
            }
        )

    def document(self) -> Dict[str, Any]:
        """Return the converted ODPG graph document."""
        return {
            "schema": SCHEMA_URL,
            "version": 1.0,
            "kind": "Graph",
            "graph": {
                "metadata": {
                    "id": self.graph_id,
                    "name": {"en": self.name},
                    "description": {"en": self.description},
                },
                "nodes": list(self.nodes_by_id.values()),
                "edges": self.edges,
            },
        }


def convert_graph(
    source: Any,
    source_format: str,
    graph_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    confidence: str = DEFAULT_CONFIDENCE,
) -> Dict[str, Any]:
    """Convert an external graph source into an ODPG graph document."""
    normalized = normalize_format(source_format)
    builder = ODPGBuilder(
        graph_id=graph_id,
        name=name,
        description=description,
        confidence=confidence,
    )

    if normalized == "jsonld":
        convert_jsonld(source, builder)
    elif normalized == "graphml":
        convert_graphml(str(source), builder)
    elif normalized == "graphson":
        convert_graphson(source, builder)
    elif normalized == "rdf":
        convert_rdf(str(source), builder)
    elif normalized in {"opencypher", "gql"}:
        convert_property_graph_script(str(source), builder)
    elif normalized == "gremlin":
        convert_gremlin(str(source), builder)
    else:
        raise ValueError("Unsupported graph format: " + source_format)

    return builder.document()


def convert_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    source_format: Optional[str] = None,
    graph_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    confidence: str = DEFAULT_CONFIDENCE,
) -> Dict[str, Any]:
    """Convert an external graph file and optionally write ODPG YAML."""
    if not input_path.is_file():
        raise FileNotFoundError("Graph file not found: " + str(input_path))

    resolved_format = normalize_format(source_format or infer_format(input_path))
    source = read_source(input_path, resolved_format)
    if resolved_format == "json":
        resolved_format = infer_json_format(source)
    document = convert_graph(
        source,
        source_format=resolved_format,
        graph_id=graph_id or input_path.stem,
        name=name,
        description=description,
        confidence=confidence,
    )
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(dump_graph_yaml(document), encoding="utf-8")
    return document


def dump_graph_yaml(document: Dict[str, Any]) -> str:
    """Serialize an ODPG graph document to YAML."""
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def normalize_format(source_format: str) -> str:
    """Normalize graph format aliases."""
    normalized = source_format.strip().lower()
    return FORMAT_ALIASES.get(normalized, normalized)


def infer_format(path: Path) -> str:
    """Infer graph format from a source filename."""
    suffix = path.suffix.lower()
    if suffix == ".jsonld":
        return "jsonld"
    if suffix == ".graphml":
        return "graphml"
    if suffix == ".graphson":
        return "graphson"
    if suffix in {".rdf", ".ttl", ".nt", ".n3"}:
        return "rdf"
    if suffix in {".cypher", ".cql"}:
        return "opencypher"
    if suffix == ".gql":
        return "gql"
    if suffix in {".gremlin", ".groovy"}:
        return "gremlin"
    if suffix == ".json":
        return "json"
    raise ValueError("Could not infer graph format from file extension: " + suffix)


def read_source(path: Path, source_format: str) -> Any:
    """Read a graph source file using the selected format."""
    text = path.read_text(encoding="utf-8-sig")
    if source_format in {"json", "jsonld", "graphson"}:
        return json.loads(text)
    return text


def infer_json_format(data: Any) -> str:
    """Infer whether a JSON graph is JSON-LD or GraphSON."""
    if isinstance(data, dict) and (
        "@graph" in data or "@context" in data or "@id" in data
    ):
        return "jsonld"
    if isinstance(data, dict) and (
        "vertices" in data or "nodes" in data or "edges" in data
    ):
        return "graphson"
    if isinstance(data, list):
        return "jsonld"
    raise ValueError(
        "JSON input must look like JSON-LD or GraphSON, or pass --format explicitly"
    )


def convert_jsonld(source: Any, builder: ODPGBuilder) -> None:
    """Convert JSON-LD nodes and object references."""
    objects = jsonld_objects(source)
    known_ids = {
        clean_identifier(item.get("@id"))
        for item in objects
        if isinstance(item, dict) and clean_identifier(item.get("@id"))
    }

    for item in objects:
        node_id = clean_identifier(item.get("@id"))
        if node_id:
            builder.add_node(node_id, jsonld_type(item.get("@type")))

    for item in objects:
        source_id = clean_identifier(item.get("@id"))
        if not source_id:
            continue
        for predicate, value in item.items():
            if predicate.startswith("@"):
                continue
            for target in jsonld_references(value):
                if target in known_ids:
                    builder.add_edge(source_id, target, predicate)


def jsonld_objects(source: Any) -> List[Dict[str, Any]]:
    """Return JSON-LD graph objects from object, array, or @graph input."""
    if isinstance(source, list):
        return [item for item in source if isinstance(item, dict)]
    if not isinstance(source, dict):
        raise ValueError("JSON-LD source must be a JSON object or array")
    graph = source.get("@graph")
    if isinstance(graph, list):
        return [item for item in graph if isinstance(item, dict)]
    if source.get("@id"):
        return [source]
    return []


def jsonld_type(value: Any) -> str:
    """Return a local ODPG node type from JSON-LD @type."""
    if isinstance(value, list):
        return local_name(clean_identifier(value[0])) if value else DEFAULT_NODE_TYPE
    return local_name(clean_identifier(value)) or DEFAULT_NODE_TYPE


def jsonld_references(value: Any) -> List[str]:
    """Return object references from a JSON-LD property value."""
    if isinstance(value, dict):
        target = clean_identifier(value.get("@id"))
        return [target] if target else []
    if isinstance(value, list):
        references = []
        for item in value:
            references.extend(jsonld_references(item))
        return references
    return []


def convert_graphml(source: str, builder: ODPGBuilder) -> None:
    """Convert GraphML nodes and directed edges."""
    root = ET.fromstring(source)
    keys: Dict[str, str] = {}
    for key in root.findall(".//{*}key"):
        key_id = clean_identifier(key.attrib.get("id"))
        attr_name = clean_identifier(key.attrib.get("attr.name"))
        if key_id and attr_name:
            keys[key_id] = attr_name

    for node in root.findall(".//{*}node"):
        node_id = clean_identifier(node.attrib.get("id"))
        if not node_id:
            continue
        data = graphml_data(node, keys)
        builder.add_node(node_id, data.get("type") or data.get("label"))

    for edge in root.findall(".//{*}edge"):
        source_id = clean_identifier(edge.attrib.get("source"))
        target_id = clean_identifier(edge.attrib.get("target"))
        if not source_id or not target_id:
            continue
        data = graphml_data(edge, keys)
        builder.add_edge(source_id, target_id, data.get("type") or data.get("label"))


def graphml_data(element: ET.Element, keys: Dict[str, str]) -> Dict[str, str]:
    """Return GraphML data values by resolved key name."""
    data = {}
    for child in element.findall("{*}data"):
        key = clean_identifier(child.attrib.get("key"))
        name = keys.get(key, key)
        if name:
            data[name] = clean_identifier(child.text)
    return data


def convert_graphson(source: Any, builder: ODPGBuilder) -> None:
    """Convert simple GraphSON vertices and edges."""
    data = unwrap_graphson(source)
    if not isinstance(data, dict):
        raise ValueError("GraphSON source must be a JSON object")

    vertices = data.get("vertices") or data.get("nodes") or data.get("V") or []
    edges = data.get("edges") or data.get("E") or []
    if isinstance(vertices, dict):
        vertices = list(vertices.values())
    if isinstance(edges, dict):
        edges = list(edges.values())

    for vertex in vertices:
        if not isinstance(vertex, dict):
            continue
        node_id = vertex.get("id") or vertex.get("_id")
        label = vertex.get("label") or vertex.get("type") or vertex.get("_label")
        if node_id is not None:
            builder.add_node(node_id, label)

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source_id = edge.get("outV") or edge.get("source") or edge.get("from")
        target_id = edge.get("inV") or edge.get("target") or edge.get("to")
        label = edge.get("label") or edge.get("type") or edge.get("_label")
        if source_id is not None and target_id is not None:
            builder.add_edge(source_id, target_id, label)


def unwrap_graphson(value: Any) -> Any:
    """Unwrap typed GraphSON @value containers."""
    if isinstance(value, dict):
        if "@value" in value and set(value.keys()).issubset({"@type", "@value"}):
            return unwrap_graphson(value["@value"])
        return {key: unwrap_graphson(item) for key, item in value.items()}
    if isinstance(value, list):
        return [unwrap_graphson(item) for item in value]
    return value


TRIPLE_RE = re.compile(
    r"^\s*(?P<s><[^>]+>|_:[A-Za-z0-9_-]+|[A-Za-z][\w.-]*:[^\s]+)\s+"
    r"(?P<p>a|<[^>]+>|[A-Za-z][\w.-]*:[^\s]+)\s+"
    r"(?P<o><[^>]+>|_:[A-Za-z0-9_-]+|[A-Za-z][\w.-]*:[^\s]+|"
    r"\"(?:\\.|[^\"])*\"(?:@\w+|\^\^<[^>]+>)?)\s*\.\s*$"
)


def convert_rdf(source: str, builder: ODPGBuilder) -> None:
    """Convert simple RDF/Turtle/N-Triples style triples."""
    typed_nodes: Dict[str, str] = {}
    edges: List[Tuple[str, str, str]] = []
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.startswith("#")
            or line.startswith("@prefix")
            or line.upper().startswith("PREFIX")
        ):
            continue
        match = TRIPLE_RE.match(line)
        if not match:
            continue
        subject = clean_rdf_term(match.group("s"))
        predicate = clean_rdf_term(match.group("p"))
        rdf_object = match.group("o")
        if rdf_object.startswith('"'):
            continue
        target = clean_rdf_term(rdf_object)
        if predicate in {"a", "rdf:type"} or local_name(predicate) == "type":
            typed_nodes[subject] = local_name(target) or DEFAULT_NODE_TYPE
        else:
            edges.append((subject, target, predicate))

    for node_id, node_type in typed_nodes.items():
        builder.add_node(node_id, node_type)
    for source_id, target_id, edge_type in edges:
        builder.add_edge(source_id, target_id, edge_type)


NODE_PATTERN = re.compile(
    r"\((?P<var>[A-Za-z_]\w*)?\s*(?::(?P<label>[A-Za-z_][\w.-]*))?"
    r"\s*(?:\{(?P<props>[^}]*)\})?\)"
)
EDGE_PATTERN = re.compile(
    r"\((?P<left>[A-Za-z_]\w*)[^\)]*\)\s*-\s*"
    r"\[\s*(?::(?P<label>[A-Za-z_][\w.-]*))?[^\]]*\]\s*->"
    r"\s*\((?P<right>[A-Za-z_]\w*)[^\)]*\)"
)
PROP_PATTERN = re.compile(r"(?P<key>[A-Za-z_]\w*)\s*:\s*['\"](?P<value>[^'\"]+)['\"]")


def convert_property_graph_script(source: str, builder: ODPGBuilder) -> None:
    """Convert simple OpenCypher and GQL node/edge patterns."""
    variables: Dict[str, str] = {}

    for match in NODE_PATTERN.finditer(source):
        variable = clean_identifier(match.group("var"))
        label = clean_identifier(match.group("label"))
        props = parse_properties(match.group("props") or "")
        if not label and not props:
            continue
        node_id = props.get("id") or props.get("name") or variable
        if node_id:
            builder.add_node(node_id, label or DEFAULT_NODE_TYPE)
            if variable:
                variables[variable] = node_id

    for match in EDGE_PATTERN.finditer(source):
        source_id = variables.get(match.group("left"), match.group("left"))
        target_id = variables.get(match.group("right"), match.group("right"))
        builder.add_edge(
            source_id, target_id, match.group("label") or DEFAULT_EDGE_TYPE
        )


def parse_properties(source: str) -> Dict[str, str]:
    """Parse simple single-quoted or double-quoted property maps."""
    return {
        match.group("key"): match.group("value")
        for match in PROP_PATTERN.finditer(source)
    }


ADD_VERTEX_RE = re.compile(
    r"addV\(['\"](?P<label>[^'\"]+)['\"]\)"
    r"(?P<props>(?:\.property\(['\"][^'\"]+['\"],\s*['\"][^'\"]+['\"]\))*)"
)
GREMLIN_PROP_RE = re.compile(
    r"\.property\(['\"](?P<key>[^'\"]+)['\"],\s*['\"](?P<value>[^'\"]+)['\"]\)"
)
ADD_EDGE_RE = re.compile(
    r"(?P<out>[A-Za-z_][\w.-]*)\.addEdge\(['\"](?P<label>[^'\"]+)['\"],"
    r"\s*(?P<in>[A-Za-z_][\w.-]*)\)"
)


def convert_gremlin(source: str, builder: ODPGBuilder) -> None:
    """Convert simple Gremlin addV/addEdge statements."""
    for match in ADD_VERTEX_RE.finditer(source):
        props = {
            prop.group("key"): prop.group("value")
            for prop in GREMLIN_PROP_RE.finditer(match.group("props"))
        }
        node_id = (
            props.get("id")
            or props.get("name")
            or "{}-{}".format(match.group("label"), len(builder.nodes_by_id) + 1)
        )
        builder.add_node(node_id, match.group("label"))

    for match in ADD_EDGE_RE.finditer(source):
        builder.add_edge(match.group("out"), match.group("in"), match.group("label"))


def clean_identifier(value: Any) -> str:
    """Return a stripped string identifier."""
    if value is None:
        return ""
    return str(value).strip()


def clean_rdf_term(value: str) -> str:
    """Remove RDF angle brackets when present."""
    cleaned = value.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return cleaned[1:-1]
    return cleaned


def local_name(value: str) -> str:
    """Return the local name of a URI, QName, or plain value."""
    cleaned = clean_rdf_term(value)
    if not cleaned:
        return ""
    for separator in ("#", "/", ":"):
        if separator in cleaned:
            cleaned = cleaned.rsplit(separator, 1)[-1]
    return cleaned
