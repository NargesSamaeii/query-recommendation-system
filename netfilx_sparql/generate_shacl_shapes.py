"""
Generates a SHACL-shapes Turtle file from netflix_ontology.owl.

web_app's SHACLSchemaParser only understands SHACL-shaped Turtle (sh:NodeShape /
sh:targetClass / sh:property), but netflix_ontology.owl is plain RDF/XML OWL with no
SHACL at all. Every class/property in the ontology already carries rdfs:domain/
rdfs:range, so the conversion is mechanical: one NodeShape per owl:Class, one
sh:property per property whose domain is that class.

Run once (or whenever netflix_ontology.owl changes) to regenerate netflix_shapes.ttl:
    python generate_shacl_shapes.py
"""

from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, BNode, Literal
from rdflib.namespace import XSD

HERE = Path(__file__).parent
OWL_PATH = HERE / "netflix_ontology.owl"
OUTPUT_PATH = HERE / "netflix_shapes.ttl"

SH = Namespace("http://www.w3.org/ns/shacl#")
EX_BASE = "http://www.semanticweb.org/exogame/ontologies/2026/4/untitled-ontology-57#"
EX = Namespace(EX_BASE)


def local_name(iri):
    iri = str(iri)
    if "#" in iri:
        return iri.rsplit("#", 1)[1]
    return iri.rsplit("/", 1)[1]


def main():
    src = Graph()
    src.parse(str(OWL_PATH), format="xml")

    classes = sorted(src.subjects(RDF.type, OWL.Class), key=str)
    object_props = set(src.subjects(RDF.type, OWL.ObjectProperty))
    datatype_props = set(src.subjects(RDF.type, OWL.DatatypeProperty))

    shapes = Graph()
    shapes.bind("sh", SH)
    shapes.bind("ex", EX)
    shapes.bind("xsd", XSD)

    for cls in classes:
        cls_name = local_name(cls)
        shape_uri = URIRef(f"{EX_BASE}{cls_name}Shape")
        shapes.add((shape_uri, RDF.type, SH.NodeShape))
        shapes.add((shape_uri, SH.targetClass, cls))

        props_for_class = [
            p for p in list(object_props) + list(datatype_props)
            if (p, RDFS.domain, cls) in src
        ]

        for prop in sorted(props_for_class, key=str):
            prop_node = BNode()
            shapes.add((shape_uri, SH.property, prop_node))
            shapes.add((prop_node, SH.path, prop))

            range_val = src.value(prop, RDFS.range)
            if prop in object_props and range_val is not None:
                shapes.add((prop_node, SH["class"], range_val))
                shapes.add((prop_node, SH.nodeKind, SH.IRI))
            elif range_val is not None:
                shapes.add((prop_node, SH.datatype, range_val))

    shapes.serialize(destination=str(OUTPUT_PATH), format="turtle")
    print(f"Wrote {len(classes)} NodeShapes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
