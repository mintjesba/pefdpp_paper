from rdflib import Graph

files = [
    "pefdpp_paper/ontology/ontology/dataquality.ttl",
    "pefdpp_paper/ontology/ontology/lci/flow.ttl",
    "pefdpp_paper/ontology/ontology/lci/activity.ttl",
    "pefdpp_paper/ontology/ontology/lci/dataset.ttl",
    "pefdpp_paper/ontology/ontology/pefstudy/lcia.ttl",
    "pefdpp_paper/ontology/ontology/pefstudy/product-system.ttl",
    "pefdpp_paper/ontology/ontology/pefstudy/pefstudy.ttl",
    "pefdpp_paper/ontology/ontology/pefdpp.ttl",
]

merged = Graph()
for f in files:
    merged.parse(f, format="turtle")

merged.serialize("pefdpp-merged.ttl", format="turtle")
