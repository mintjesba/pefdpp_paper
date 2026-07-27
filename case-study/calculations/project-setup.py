# %% Set up brightway project
import brightway2 as bw

bw.projects.set_current("ecoinvent312")

ei = bw.Database("ecoinvent3.12-cutoff")

# %%
ei.search("")

# %% Load PEFDPP ontology + ecoinvent case-study dataset
from pathlib import Path
from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_DIR = REPO_ROOT / "ontology" / "ontology"

ontology_files = [
    ONTOLOGY_DIR / "dataquality.ttl",
    ONTOLOGY_DIR / "lci" / "flow.ttl",
    ONTOLOGY_DIR / "lci" / "activity.ttl",
    ONTOLOGY_DIR / "lci" / "dataset.ttl",
    ONTOLOGY_DIR / "pefstudy" / "lcia.ttl",
    ONTOLOGY_DIR / "pefstudy" / "product-system.ttl",
    ONTOLOGY_DIR / "pefstudy" / "pefstudy.ttl",
    ONTOLOGY_DIR / "pefdpp.ttl",
]

g = Graph()
for f in ontology_files:
    g.parse(f, format="turtle")

g.parse(
    REPO_ROOT / "case-study" / "lcidatasets" / "secondary" / "ecoinvent.ttl",
    format="turtle",
)

# %% Extract FlowTypes sourced from ecoinvent, keyed by their rdfs:label
from rdflib import Namespace, RDF, RDFS

FLOW = Namespace("https://w3id.org/mintjesba/pefdpp/flow#")
ECOINVENT_DATASET = Namespace(
    "https://w3id.org/mintjesba/pefdpp/cases/battery-pack/ecoinvent#"
)["ecoinvent"]

flow_types = []
for flow_class in (FLOW.ProductFlow, FLOW.WasteFlow, FLOW.ElementaryFlow):
    for ft in g.subjects(RDF.type, flow_class):
        if (ft, FLOW.sourcedFrom, ECOINVENT_DATASET) not in g:
            continue
        label = g.value(ft, RDFS.label)
        flow_types.append({"uri": ft, "label": str(label) if label else None})

print(f"Found {len(flow_types)} FlowTypes sourced from ecoinvent")

# %% Index the ecoinvent3.12 database by activity name and reference product for label matching
from collections import defaultdict

ei_by_name = defaultdict(list)
ei_by_product = defaultdict(list)
for act in ei:
    ei_by_name[act["name"].strip().lower()].append(act)
    product = act.get("reference product")
    if product:
        ei_by_product[product.strip().lower()].append(act)

all_names = list(ei_by_name.keys())
all_products = list(ei_by_product.keys())

# %% Match each FlowType's label to ecoinvent3.12 activities
# Tries exact match on activity name, then reference product, then falls back to
# fuzzy string matching (stdlib difflib) against both when there is no exact hit.
# Deliberately does NOT pick a single preferred location here: FlowType is location-
# agnostic in the ontology (location is resolved at the Flow level), and matching by
# activity would smuggle a location back in. All location-variant candidates are kept
# and reconciled via their shared product-flow UUID in the next cell.
import difflib

FUZZY_CUTOFF = 0.85


def fuzzy_match(label):
    scored = []
    for pool, index in ((all_names, ei_by_name), (all_products, ei_by_product)):
        for name in difflib.get_close_matches(label, pool, n=10, cutoff=FUZZY_CUTOFF):
            ratio = difflib.SequenceMatcher(None, label, name).ratio()
            scored.append((ratio, name, index[name]))
    if not scored:
        return [], None
    best_score = max(ratio for ratio, _, _ in scored)
    top = [(name, acts) for ratio, name, acts in scored if ratio == best_score]
    candidates, seen = [], set()
    for _, acts in top:
        for a in acts:
            if a["code"] not in seen:
                seen.add(a["code"])
                candidates.append(a)
    return candidates, best_score


for row in flow_types:
    label = row["label"].strip().lower() if row["label"] else None
    row["match_method"] = None
    candidates = []

    if label:
        candidates = ei_by_name.get(label, [])
        if candidates:
            row["match_method"] = "exact-name"
        else:
            candidates = ei_by_product.get(label, [])
            if candidates:
                row["match_method"] = "exact-product"

        if not candidates:
            candidates, score = fuzzy_match(label)
            if candidates:
                row["match_method"] = f"fuzzy ({score:.2f})"

    row["matches"] = candidates

n_matched = sum(1 for r in flow_types if r["matches"])
print(f"{n_matched} of {len(flow_types)} labels matched at least one activity")

# %% Diagnostic: does this ecoinvent import preserve a location-agnostic product-flow UUID?
# Real ecoinvent assigns one "intermediate exchange" UUID per product, shared by every
# location-variant activity that produces it — distinct from the (per-location) activity
# UUID in act["code"]. Whether bw2io kept that on the production exchange's "flow" key
# depends on how this database was imported, so check on one example before trusting it.
sample = next((r for r in flow_types if r["matches"]), None)
if sample:
    sample_act = sample["matches"][0]
    sample_exc = next(iter(sample_act.production()), None)
    if sample_exc is None:
        print(
            f"WARNING: {sample_act['name']!r} has no production exchange — inspect manually."
        )
    else:
        print("Production exchange keys:", sorted(sample_exc.as_dict().keys()))
        print("exc.get('flow') ->", sample_exc.get("flow"))
        print("act['code']     ->", sample_act["code"])
        print(
            "If 'flow' is None or always equal to act['code'], this import did not keep"
        )
        print(
            "ecoinvent's location-agnostic flow UUID and the activity-code fallback below is the best available."
        )


def production_flow_code(act):
    exc = next(iter(act.production()), None)
    return exc.get("flow") if exc is not None else None


# %% Reconcile candidates per label via their shared product-flow UUID (falls back to
# activity code only when no 'flow' UUID is available on the production exchange)
for row in flow_types:
    codes = {production_flow_code(a) for a in row["matches"]}
    codes.discard(None)
    row["flow_codes"] = sorted(codes)
    if not row["flow_codes"]:
        row["flow_codes"] = sorted({a["code"] for a in row["matches"]})
        row["flow_code_is_activity_fallback"] = bool(row["matches"])
    else:
        row["flow_code_is_activity_fallback"] = False

resolved = [r for r in flow_types if len(r["flow_codes"]) == 1]
ambiguous = [r for r in flow_types if len(r["flow_codes"]) > 1]
unmatched = [r for r in flow_types if not r["matches"]]
print(
    f"{len(resolved)} resolved, {len(ambiguous)} ambiguous, {len(unmatched)} unmatched (of {len(flow_types)})"
)

# %% Write resolved matches back into the graph as flow:sameAsSecondaryFlowType
from rdflib import Literal

for row in resolved:
    g.set((row["uri"], FLOW.sameAsSecondaryFlowType, Literal(row["flow_codes"][0])))

# %% Review resolved-via-fuzzy or activity-code-fallback matches — spot-check these
for row in resolved:
    if (
        row["match_method"]
        and row["match_method"].startswith("fuzzy")
        or row["flow_code_is_activity_fallback"]
    ):
        name = row["uri"].split("#", 1)[-1]
        flag = (
            "activity-code fallback"
            if row["flow_code_is_activity_fallback"]
            else row["match_method"]
        )
        print(
            f"{name!r:60s} label={row['label']!r:50s} -> {row['flow_codes'][0]!r} [{flag}]"
        )

# %% Review FlowTypes that still need manual matching
for row in ambiguous + unmatched:
    name = row["uri"].split("#", 1)[-1]
    print(
        f"{name!r:60s} label={row['label']!r:50s} flow_codes={row['flow_codes']} method={row['match_method']}"
    )

# %%#
flow_code_to_name = {}
for act in ei:
    for exc in act.production():
        code = exc.get("flow")
        if code:
            flow_code_to_name[code] = exc.get("name") or act["reference product"]
