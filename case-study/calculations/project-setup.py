# %% Import modules
import brightway2 as bw
from collections import defaultdict

from pathlib import Path
from rdflib import Graph, Namespace, RDF

# %% Load the ontology and case study into one graph
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
    ONTOLOGY_DIR / "skos" / "pef-geographies.ttl",
]

case_study_files = [
    REPO_ROOT / "case-study" / "lcidatasets" / "secondary" / "ecoinvent.ttl",
    REPO_ROOT / "case-study" / "lcidatasets" / "secondary" / "battery-eol.ttl",
    REPO_ROOT / "case-study" / "lcidatasets" / "secondary" / "biosphere.ttl",
    REPO_ROOT / "case-study" / "lcidatasets" / "dpp" / "battery-pack.ttl",
    REPO_ROOT / "case-study" / "lcidatasets" / "dpp" / "battery-cell.ttl",
    REPO_ROOT / "case-study" / "lcidatasets" / "dpp" / "battery-module.ttl",
    REPO_ROOT / "case-study" / "lcidatasets" / "dpp" / "brazing.ttl",
    REPO_ROOT / "case-study" / "battery-pef.ttl",
]

g = Graph()
for f in ontology_files + case_study_files:
    g.parse(f, format="turtle")

FLOW = Namespace("https://w3id.org/mintjesba/pefdpp/flow#")
ACT = Namespace("https://w3id.org/mintjesba/pefdpp/activity#")

# %% Set up all Brightway and ecoinvent requirements
# %%% Set up brightway project (ecoinvent3.12 preloaded)
bw.projects.set_current("ecoinvent312")
ei = bw.Database("ecoinvent-3.12-cutoff")


# %%% Set up a dict linking ecoinvent flowtypes to all their producing activities
def get_flow_uuid(act):
    exc = next(iter(act.production()), None)
    return exc.get("flow") if exc is not None else None


flow_uuid_to_activities = defaultdict(list)
for act in ei:
    uuid = get_flow_uuid(act)
    if uuid:
        flow_uuid_to_activities[uuid].append(act)

print(
    f"Indexed {len(flow_uuid_to_activities)} distinct flow UUIDs "
    f"across {sum(len(v) for v in flow_uuid_to_activities.values())} activities"
)


def activity_location(act_uri):
    """The ecoinvent-style location code (e.g. 'RER') for a case-study act:Activity,
    read off its act:hasGeography -> skos:notation."""
    if act_uri is None:
        return None
    geography = g.value(act_uri, ACT.hasGeography)
    if geography is None:
        return None
    notation = g.value(geography, SKOS.notation)
    return str(notation) if notation else None


def resolve_flow_uuid(flow_uuid, preferred_location=None):
    """Pick one specific activity to represent a location-agnostic ecoinvent flow
    UUID, so it can actually be used as an LCA demand.

    Preference order:
      1. If exactly one 'market for X' / 'market group for X' activity shares this
         UUID, use it — matches how ecoinvent itself aggregates location-variant
         suppliers into one representative average, and is the standard choice for
         an ordinary (non-CFF) input flow.
      2. If several market activities share it, narrow to those. Within that pool
         (or the full candidate pool if there was no market activity), prefer the
         one whose location matches `preferred_location` — the geography of the
         case-study activity this flow actually appears in, not a fixed guess.
      3. If that doesn't resolve it, fall back to the generic PREFERRED_LOCATIONS
         order (GLO, then RoW, then RER).
      4. Final fallback: sort by (location, name, code) and take the first, so the
         choice is at least stable across runs even when none of the above apply.
    """
    candidates = flow_uuid_to_activities.get(flow_uuid, [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    market = [
        a
        for a in candidates
        if a["name"].strip().lower().startswith(("market for", "market group for"))
    ]
    pool = market if market else candidates

    if preferred_location:
        exact = [a for a in pool if a["location"] == preferred_location]
        if len(exact) == 1:
            return exact[0]

    for loc in PREFERRED_LOCATIONS:
        loc_matches = [a for a in pool if a["location"] == loc]
        if len(loc_matches) == 1:
            return loc_matches[0]

    return sorted(pool, key=lambda a: (a["location"], a["name"], a["code"]))[0]


# %%% Set up a dict linking ecoinvent activity UUIDs to the activities in the bw.Database
ecoinvent_activity_id_to_activity = {}
for act in ei:
    activity_id = act.get("activity")
    if activity_id:
        ecoinvent_activity_id_to_activity[activity_id] = act

print(
    f"Indexed {len(ecoinvent_activity_id_to_activity)} ecoinvent ActivityIds "
    f"across {len(ei)} activities"
)
# %% Load the ontology + case study into one graph
# Fallback order only used when a flow instance has no usable geography context
# of its own (e.g. no consuming activity, or that activity has no act:hasGeography).
PREFERRED_LOCATIONS = ["RER", "RoW", "GLO"]

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


def activity_location(act_uri):
    """The ecoinvent-style location code (e.g. 'RER') for a case-study act:Activity,
    read off its act:hasGeography -> skos:notation."""
    if act_uri is None:
        return None
    geography = g.value(act_uri, ACT.hasGeography)
    if geography is None:
        return None
    notation = g.value(geography, SKOS.notation)
    return str(notation) if notation else None


def resolve_flow_uuid(flow_uuid, preferred_location=None):
    """Pick one specific activity to represent a location-agnostic ecoinvent flow
    UUID, so it can actually be used as an LCA demand.

    Preference order:
      1. If exactly one 'market for X' / 'market group for X' activity shares this
         UUID, use it — matches how ecoinvent itself aggregates location-variant
         suppliers into one representative average, and is the standard choice for
         an ordinary (non-CFF) input flow.
      2. If several market activities share it, narrow to those. Within that pool
         (or the full candidate pool if there was no market activity), prefer the
         one whose location matches `preferred_location` — the geography of the
         case-study activity this flow actually appears in, not a fixed guess.
      3. If that doesn't resolve it, fall back to the generic PREFERRED_LOCATIONS
         order (GLO, then RoW, then RER).
      4. Final fallback: sort by (location, name, code) and take the first, so the
         choice is at least stable across runs even when none of the above apply.
    """
    candidates = flow_uuid_to_activities.get(flow_uuid, [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    market = [
        a
        for a in candidates
        if a["name"].strip().lower().startswith(("market for", "market group for"))
    ]
    pool = market if market else candidates

    if preferred_location:
        exact = [a for a in pool if a["location"] == preferred_location]
        if len(exact) == 1:
            return exact[0]

    for loc in PREFERRED_LOCATIONS:
        loc_matches = [a for a in pool if a["location"] == loc]
        if len(loc_matches) == 1:
            return loc_matches[0]

    return sorted(pool, key=lambda a: (a["location"], a["name"], a["code"]))[0]


# %% Resolve every ecoinvent-sourced flow:Flow instance's UUID, using the geography
# of whichever case-study activity it's actually an input/output of — not the
# FlowType alone, since the same location-agnostic FlowType can legitimately
# resolve differently depending on where in the product system it's being used.
from rdflib import RDF

flow_instance_resolution = {}
for flow_instance in g.subjects(RDF.type, FLOW.Flow):
    flow_type = g.value(flow_instance, FLOW.hasFlowType)
    if flow_type is None:
        continue
    if (flow_type, RDF.type, FLOW.ElementaryFlow) in g:
        continue  # resolved against biosphere3 below, not ecoinvent's technosphere
    uuid = g.value(flow_type, FLOW.sameAsSecondaryFlowType)
    if uuid is None:
        continue

    consuming_act = g.value(flow_instance, ACT.inputOf) or g.value(
        flow_instance, ACT.outputOf
    )
    location = activity_location(consuming_act)
    flow_instance_resolution[flow_instance] = resolve_flow_uuid(str(uuid), location)

resolved_fi = {k: v for k, v in flow_instance_resolution.items() if v is not None}
unresolved_fi = {k: v for k, v in flow_instance_resolution.items() if v is None}
print(
    f"{len(resolved_fi)} flow instances resolved to a runnable activity, "
    f"{len(unresolved_fi)} unresolved (of {len(flow_instance_resolution)})"
)
for fi in unresolved_fi:
    print("UNRESOLVED — flow UUID not found in this database:", fi)

# %% Spot-check a sample of resolutions before trusting them
for fi, act in list(resolved_fi.items())[:15]:
    name = fi.split("#", 1)[-1]
    print(f"{name:55s} -> {act['name']} ({act['location']})")

# %% Resolve every act:sameAsSecondaryActivity to a real ecoinvent activity
# act:sameAsSecondaryActivity stores ecoinvent's own canonical ActivityId
# (act.get("activity")) rather than bw2io's internal act["code"] hash — the former
# is stable across re-imports and the right thing to persist in the ontology, but
# Database.get()/ei.get() only ever looks up by "code", so it can't be used
# directly. Build a reverse index from ecoinvent ActivityId -> Activity instead.

activity_resolution = {}
for a in g.subjects(ACT.sameAsSecondaryActivity, None):
    activity_id = str(g.value(a, ACT.sameAsSecondaryActivity))
    activity_resolution[a] = ecoinvent_activity_id_to_activity.get(activity_id)

resolved_act = {k: v for k, v in activity_resolution.items() if v is not None}
unresolved_act = {k: v for k, v in activity_resolution.items() if v is None}
print(
    f"{len(resolved_act)} act:Activity individuals resolved, "
    f"{len(unresolved_act)} unresolved (of {len(activity_resolution)})"
)
for a in unresolved_act:
    code = str(g.value(a, ACT.sameAsSecondaryActivity))
    print(f"UNRESOLVED — activity code not found: {a} ({code})")

# %% Resolve every ElementaryFlow's flow:sameAsSecondaryFlowType to a real
# biosphere3 flow. This is a separate index from the ecoinvent technosphere
# resolver above: elementary flows live in "biosphere3", not
# "ecoinvent-3.12-cutoff", and biosphere3's own flow codes are ecoinvent-native
# UUIDs — different from the JRC EF3.1 UUIDs used for skos:exactMatch, which
# is why sameAsSecondaryFlowType (not skos:exactMatch) is what gets resolved.
bio = bw.Database("biosphere3")
biosphere_uuid_to_flow = {f["code"]: f for f in bio}

print(f"Indexed {len(biosphere_uuid_to_flow)} biosphere3 flows")

elementary_flow_resolution = {}
for flow_instance in g.subjects(RDF.type, FLOW.Flow):
    flow_type = g.value(flow_instance, FLOW.hasFlowType)
    if flow_type is None or (flow_type, RDF.type, FLOW.ElementaryFlow) not in g:
        continue
    uuid = g.value(flow_type, FLOW.sameAsSecondaryFlowType)
    if uuid is None:
        continue
    elementary_flow_resolution[flow_instance] = biosphere_uuid_to_flow.get(str(uuid))

resolved_bio = {k: v for k, v in elementary_flow_resolution.items() if v is not None}
unresolved_bio = {k: v for k, v in elementary_flow_resolution.items() if v is None}
print(
    f"{len(resolved_bio)} elementary flow instances resolved to biosphere3, "
    f"{len(unresolved_bio)} unresolved (of {len(elementary_flow_resolution)})"
)
for fi in unresolved_bio:
    uuid = g.value(g.value(fi, FLOW.hasFlowType), FLOW.sameAsSecondaryFlowType)
    print(f"UNRESOLVED — biosphere3 UUID not found: {fi} ({uuid})")

for fi, flow in list(resolved_bio.items())[:15]:
    name = fi.split("#", 1)[-1]
    print(f"{name:45s} -> {flow['name']} {flow['categories']}")

# %% Step 2: Build the foreground product system as Brightway Databases
# One bw.Database per case-study dataset:LCIDataset, one Activity per
# act:Activity, exchanges per flow:Flow — resolved via (in priority order):
#   1. flow:hasCFFScenario  -> weighted technosphere exchanges (CFF decomposition)
#   2. flow:sameAsSecondaryFlowType -> the ecoinvent activity resolved in Step 1
#   3. an internal match: another case-study activity's own product/output
#   4. flow:ElementaryFlow -> a biosphere3 exchange (flow:sameAsSecondaryFlowType,
#      resolved above into `resolved_bio`)
from rdflib import RDFS

DATASET = Namespace("https://w3id.org/mintjesba/pefdpp/dataset#")
DCTERMS = Namespace("http://purl.org/dc/terms/")
OM = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")

UNIT_MAP = {
    "Kilogram": "kilogram",
    "kilowattHour": "kilowatt hour",
    "Megajoule": "megajoule",
    "TonneKilometre": "ton kilometer",
    "kilometre": "kilometer",
}


def bw_unit(unit_uri):
    if unit_uri is None:
        return "unit"
    local = unit_uri.split("#", 1)[-1]
    return UNIT_MAP.get(local, local)


def determining_flow(act_uri):
    return g.value(act_uri, ACT.hasDeterminingFlow)


def flow_amount(flow_uri):
    if flow_uri is None:
        return None
    measure = g.value(flow_uri, FLOW.hasMeasure)
    if measure is None:
        return None
    value = g.value(measure, OM.hasNumericalValue)
    return float(value) if value is not None else None


def flow_unit(flow_uri):
    measure = g.value(flow_uri, FLOW.hasMeasure) if flow_uri is not None else None
    return g.value(measure, OM.hasUnit) if measure is not None else None


def activity_label(act_uri):
    det = determining_flow(act_uri)
    label = g.value(det, FLOW.contextualLabel) if det is not None else None
    if label is None and det is not None:
        flow_type = g.value(det, FLOW.hasFlowType)
        label = g.value(flow_type, RDFS.label) if flow_type is not None else None
    return str(label) if label else act_uri.split("#")[-1]


def is_elementary(flow_type):
    return flow_type is not None and (flow_type, RDF.type, FLOW.ElementaryFlow) in g


def needs_internal_resolution(flow_type):
    """Whether a FlowType should be looked up in the case-study's own
    activities, rather than resolved via ecoinvent or biosphere3."""
    if flow_type is None:
        return False
    if is_elementary(flow_type):
        return False
    if (flow_type, FLOW.sameAsSecondaryFlowType, None) in g:
        return False
    return True


# %% Discover buildable act:Activity individuals per LCIDataset.
# Skipped: activities carrying act:sameAsSecondaryActivity (ecoinvent pointers,
# already resolved via `resolved_act` above — not built as new activities), and
# activities with no act:hasDeterminingFlow (stubs, e.g. battery-pef.ttl's
# AggregatedLCI placeholder). A dataset with nothing buildable (ecoinvent itself,
# biosphere.ttl) is skipped entirely.
lci_datasets = []
for ds in g.subjects(RDF.type, DATASET.LCIDataset):
    buildable = [
        a
        for a in g.objects(ds, DATASET.containsActivity)
        if (a, ACT.sameAsSecondaryActivity, None) not in g
        and (a, ACT.hasDeterminingFlow, None) in g
    ]
    if buildable:
        title = g.value(ds, DCTERMS.title)
        db_name = str(title) if title else ds.split("#")[-1]
        lci_datasets.append((ds, db_name, buildable))

print(f"Building {len(lci_datasets)} Brightway databases:")
for ds, db_name, activities in lci_datasets:
    print(f"  {db_name}: {len(activities)} activities")

# %% Assign every buildable activity a Brightway key, and index which
# case-study activity produces each internally-resolvable FlowType. Reference
# (determining-flow) producers take priority over non-reference co-product
# producers, so e.g. BatteryCellToTreatment resolves to the activity whose
# actual product it is, not to the disassembly activity that also emits it as
# a byproduct.
activity_uri_to_key = {}
for ds, db_name, activities in lci_datasets:
    for act_uri in activities:
        activity_uri_to_key[act_uri] = (db_name, act_uri.split("#")[-1])

flowtype_to_producer = {}
for ds, db_name, activities in lci_datasets:
    for act_uri in activities:
        det = determining_flow(act_uri)
        ft = g.value(det, FLOW.hasFlowType)
        if needs_internal_resolution(ft):
            flowtype_to_producer[ft] = (act_uri, det)

for ds, db_name, activities in lci_datasets:
    for act_uri in activities:
        det = determining_flow(act_uri)
        for out_flow in g.subjects(ACT.outputOf, act_uri):
            if out_flow == det:
                continue
            ft = g.value(out_flow, FLOW.hasFlowType)
            if needs_internal_resolution(ft):
                flowtype_to_producer.setdefault(ft, (act_uri, out_flow))

print(
    f"Indexed {len(activity_uri_to_key)} case-study activities, "
    f"{len(flowtype_to_producer)} internally-produced FlowTypes"
)


# %% Resolve any act:Activity URI — case-study or ecoinvent pointer — to a
# (brightway_key, reference_amount) pair, so CFF endpoints and internal links
# can be resolved through the same lookup regardless of where they point.
def resolve_activity_endpoint(act_uri):
    if act_uri in activity_uri_to_key:
        ref_amount = flow_amount(determining_flow(act_uri)) or 1.0
        return activity_uri_to_key[act_uri], ref_amount
    ei_act = resolved_act.get(act_uri)
    if ei_act is not None:
        exc = next(iter(ei_act.production()), None)
        ref_amount = exc["amount"] if exc is not None else 1.0
        return (ei_act["database"], ei_act["code"]), ref_amount
    return None, None


def cff_param(scenario_uri, prop, default=0.0):
    node = g.value(scenario_uri, prop)
    if node is None:
        return default
    value = g.value(node, FLOW.hasValue)
    return float(value) if value is not None else default


def cff_terms(scenario_uri):
    """The (property, coefficient) pairs for a flow:CFFScenario, per the PEF
    Circular Footprint Formula:
      M = (1-R1)E_V + R1(A*E_recycled + (1-A)*E_V*Qsin) + (1-A)*R2*(E_recycling - E_V*Qsout)
      E = R3(1-B)(E_ER - LHV*(Xheat*E_heat + Xelec*E_elec))
      D = (1-R2-R3)*E_D
    virginMaterialActivity/recycledMaterialActivity carry the *acquisition*-side
    burden (how the material was sourced); everything else is *end-of-life*
    (recycling-process burden, avoided-virgin credit, disposal, energy
    recovery). Kept as separate named sets (CFF_ACQUISITION_PROPS/
    CFF_EOL_PROPS below) so the two sides can be routed to different
    activities/life-cycle stages instead of both landing on whichever
    activity declares flow:hasCFFScenario.
    """
    A = cff_param(scenario_uri, FLOW.allocationFactorA)
    B = cff_param(scenario_uri, FLOW.allocationFactorB)
    R1 = cff_param(scenario_uri, FLOW.recycledContentRateR1)
    R2 = cff_param(scenario_uri, FLOW.recyclingRateR2)
    R3 = cff_param(scenario_uri, FLOW.energyRecoveryRateR3)
    Qin = cff_param(scenario_uri, FLOW.qualityRatioIn, default=1.0)
    Qout = cff_param(scenario_uri, FLOW.qualityRatioOut, default=1.0)
    LHV = cff_param(scenario_uri, FLOW.ERLowerHeatingValue)
    Xheat = cff_param(scenario_uri, FLOW.heatEREfficiency)
    Xelec = cff_param(scenario_uri, FLOW.electricityEREfficiency)

    terms = [
        (FLOW.virginMaterialActivity, (1 - R1) + R1 * (1 - A) * Qin),
        (FLOW.recycledMaterialActivity, R1 * A),
        (FLOW.recyclingActivity, (1 - A) * R2),
        (FLOW.substitutedVirginActivity, -(1 - A) * R2 * Qout),
        (FLOW.disposalActivity, 1 - R2 - R3),
    ]
    if R3:
        terms += [
            (FLOW.energyRecoveryActivity, R3 * (1 - B)),
            (FLOW.substitutedHeatActivity, -R3 * (1 - B) * LHV * Xheat),
            (FLOW.substitutedElectricityActivity, -R3 * (1 - B) * LHV * Xelec),
        ]
    return terms


CFF_ACQUISITION_PROPS = {FLOW.virginMaterialActivity, FLOW.recycledMaterialActivity}
CFF_EOL_PROPS = {
    FLOW.recyclingActivity,
    FLOW.substitutedVirginActivity,
    FLOW.disposalActivity,
    FLOW.energyRecoveryActivity,
    FLOW.substitutedHeatActivity,
    FLOW.substitutedElectricityActivity,
}

# Manufacturing-stage FlowTypes representing the same physical material as a
# flow:CFFScenario elsewhere in the product system (mapped to the matching
# CFF acquisition wrapper's material name -- see cff_acquisition_key). Their
# raw declared amounts are stated per 1 unit of *their own* activity's scale,
# not per 1 kg of the overall battery, so they can't be compared directly
# against the CFF-tracked waste amount (also per 1 kg battery) without first
# rescaling by that activity's own activation level -- see
# "Compute each foreground activity's own activation scale" below.
CFF_TRACKED_ACQUISITION_FLOWTYPES = {
    "ReinforcingSteel": "Steel",
    "Copper": "Copper",
    "CopperCollectorFoilForLiIonBattery": "Copper",
    "AluminiumWroughtAlloy": "Aluminium",
    "AluminiumCollectorFoilForLiIonBattery": "Aluminium",
}
# References to the actual exchange dicts created for those flows (mutated
# in place once the true, scale-corrected mass is known), plus enough info to
# compute that mass: (host activity key, exchange dict, raw declared amount,
# host activity's own URI, material name).
cff_tracked_exchange_refs = []


def cff_exchanges(scenario_uri, amount, props):
    """Resolve the subset of a CFFScenario's terms in `props` into weighted
    (key, amount) technosphere exchanges, given the physical amount of
    material the scenario is scaled by."""
    results = []
    for prop, coeff in cff_terms(scenario_uri):
        if prop not in props or coeff == 0:
            continue
        target = g.value(scenario_uri, prop)
        if target is None:
            continue
        key, ref_amount = resolve_activity_endpoint(target)
        if key is None:
            print(f"UNRESOLVED CFF endpoint — {prop.split('#')[-1]} on {scenario_uri}")
            continue
        results.append((key, coeff * amount / ref_amount))
    return results


SYNTHETIC_ACQUISITION_STAGE = "RawMaterialAcquisition"


def cff_acquisition_key(scenario_uri, db_name):
    """A synthetic brightway key for a CFFScenario's raw-material-acquisition
    "pseudo-activity" (e.g. AluminiumCFFScenario -> (db_name, "Aluminium
    Acquisition")), used to route the acquisition-side CFF terms
    (virginMaterialActivity/recycledMaterialActivity) onto their own
    life-cycle-stage bucket instead of wherever the CFFScenario itself is
    declared (an EndOfLife activity) -- which would otherwise misattribute
    that burden to EndOfLife in stage_contributions().

    This is a pure implementation-level construct, not backed by any RDF
    individual: the ontology and case study treat a CFFScenario as one
    unified formula application (per the official PEF CFF), and the split
    into two brightway "activities" purely for stage-reporting purposes is an
    artifact of this script, not a case-study modelling decision.
    """
    local = scenario_uri.split("#")[-1]
    if not local.endswith("CFFScenario"):
        return None
    material = local[: -len("CFFScenario")]
    return (db_name, f"{material} Acquisition")


# %% Build the full exchange list for every activity in one pass, so
# cross-activity and cross-database links all resolve regardless of build
# order, then report what did/didn't resolve before writing anything to
# Brightway.
db_data = {db_name: {} for _, db_name, _ in lci_datasets}
unresolved_flows = []
# CFF acquisition-side exchanges, keyed by the wrapper activity's own
# brightway key, accumulated here and merged into db_data after this loop
# (the wrapper's own db_data entry, built when the loop reaches it, must
# already exist before exchanges can be appended to it).
wrapper_exchange_contributions = {}

for ds, db_name, activities in lci_datasets:
    for act_uri in activities:
        key = activity_uri_to_key[act_uri]
        det = determining_flow(act_uri)
        ref_amount = flow_amount(det) or 1.0

        exchanges = [{"input": key, "amount": ref_amount, "type": "production"}]

        input_flows = set(g.subjects(ACT.inputOf, act_uri))
        output_flows = set(g.subjects(ACT.outputOf, act_uri))
        output_flows.discard(det)

        for flow_uri in input_flows | output_flows:
            is_output = flow_uri in output_flows
            amount = flow_amount(flow_uri)
            flow_type = g.value(flow_uri, FLOW.hasFlowType)
            scenario = g.value(flow_uri, FLOW.hasCFFScenario)

            if amount is None:
                unresolved_flows.append((act_uri, flow_uri, "no measure"))
                continue

            # NOT amount / ref_amount: the production exchange above already
            # uses ref_amount (not 1.0) as its own amount, so "1 unit of this
            # activity's own scale" already corresponds to ref_amount kg of
            # its reference product -- exactly what every other flow's raw
            # amount is stated relative to (e.g. MetalTreatmentAct's reagent
            # quantities are all "per 0.577 kg treatment", matching its own
            # ref_amount=0.577 kg). Dividing by ref_amount here as well would
            # double-apply that scaling. This is a no-op wherever
            # ref_amount == 1 (nearly everywhere in this case study).
            norm_amount = amount

            if scenario is not None:
                exchanges += [
                    {"input": k, "amount": a, "type": "technosphere"}
                    for k, a in cff_exchanges(scenario, norm_amount, CFF_EOL_PROPS)
                ]

                wrapper_key = cff_acquisition_key(scenario, db_name)
                # coefficients under CFF_ACQUISITION_PROPS sum to exactly
                # (1-R1)+R1 = 1 (given Qin=1), so this is a 1:1 pull: one unit
                # of waste mass maps to one unit of the synthetic wrapper's
                # own "1 kg, acquired" reference.
                exchanges.append(
                    {"input": wrapper_key, "amount": norm_amount, "type": "technosphere"}
                )
                # The wrapper's own recipe (how much virgin/recycled-content
                # material 1 kg of it costs) depends only on the CFFScenario's
                # parameters, not on which flow/activity references it -- so
                # it must be computed once per material, not once per
                # referencing flow. Multiple flows (e.g.
                # BatteryDisassemblyAct_flow2_AluminiumWaste and
                # MetalTreatmentAct_flow12_AluminiumWaste both sharing
                # AluminiumCFFScenario) each add their own *pull* amount above
                # via `wrapper_key`'s exchange on `exchanges`, but must NOT
                # each re-add the recipe itself, or the wrapper ends up
                # double-demanding its own inputs.
                if wrapper_key not in wrapper_exchange_contributions:
                    wrapper_exchange_contributions[wrapper_key] = [
                        {"input": k, "amount": a, "type": "technosphere"}
                        for k, a in cff_exchanges(scenario, 1.0, CFF_ACQUISITION_PROPS)
                    ]
                continue

            if is_elementary(flow_type):
                bio_flow = resolved_bio.get(flow_uri)
                if bio_flow is None:
                    unresolved_flows.append(
                        (
                            act_uri,
                            flow_uri,
                            "elementary flow not resolved to biosphere3",
                        )
                    )
                    continue
                exchanges.append(
                    {
                        "input": (bio_flow["database"], bio_flow["code"]),
                        "amount": norm_amount,
                        "type": "biosphere",
                    }
                )
                continue

            if flow_uri in resolved_fi:
                ei_act = resolved_fi[flow_uri]
                exc = next(iter(ei_act.production()), None)
                producer_ref = exc["amount"] if exc is not None else 1.0
                new_exchange = {
                    "input": (ei_act["database"], ei_act["code"]),
                    "amount": norm_amount / producer_ref,
                    "type": "technosphere",
                }
                exchanges.append(new_exchange)

                material = CFF_TRACKED_ACQUISITION_FLOWTYPES.get(
                    flow_type.split("#")[-1] if flow_type is not None else None
                )
                if material is not None:
                    cff_tracked_exchange_refs.append((key, new_exchange, amount, material))
                continue

            if flow_type in flowtype_to_producer:
                producer_uri, producer_flow = flowtype_to_producer[flow_type]
                if is_output and producer_uri == act_uri:
                    # this activity's own non-reference co-product — the
                    # exchange is created from the consuming side instead.
                    continue
                producer_key = activity_uri_to_key[producer_uri]
                producer_ref = flow_amount(determining_flow(producer_uri)) or 1.0
                producer_rate = flow_amount(producer_flow) / producer_ref
                exchanges.append(
                    {
                        "input": producer_key,
                        "amount": norm_amount / producer_rate,
                        "type": "technosphere",
                    }
                )
                continue

            unresolved_flows.append(
                (act_uri, flow_uri, "no CFF / ecoinvent / internal / biosphere match")
            )

        db_data[db_name][key] = {
            "name": activity_label(act_uri),
            "reference product": activity_label(act_uri),
            "unit": bw_unit(flow_unit(det)),
            "location": activity_location(act_uri) or "GLO",
            "exchanges": exchanges,
        }

# %% Materialize the synthetic per-material CFF acquisition pseudo-activities
# (e.g. "Aluminium Acquisition") -- code-only constructs, not backed by any
# RDF individual, so built here from scratch rather than merged into an
# existing db_data entry.
for wrapper_key, contributions in wrapper_exchange_contributions.items():
    wrapper_db, wrapper_code = wrapper_key
    material = wrapper_code.rsplit(" ", 1)[0]
    db_data[wrapper_db][wrapper_key] = {
        "name": f"{material}, acquired (virgin + recycled-content mix)",
        "reference product": f"{material}, acquired (virgin + recycled-content mix)",
        "unit": "kilogram",
        "location": "GLO",
        "exchanges": [
            {"input": wrapper_key, "amount": 1.0, "type": "production"},
            *contributions,
        ],
    }

n_activities = sum(len(d) for d in db_data.values())
n_exchanges = sum(len(a["exchanges"]) for d in db_data.values() for a in d.values())
print(f"Built {n_exchanges} exchanges across {n_activities} activities")
print(f"{len(unresolved_flows)} flows could not be resolved:")
for act_uri, flow_uri, reason in unresolved_flows:
    print(f"  {act_uri.split('#')[-1]:35s} {flow_uri.split('#')[-1]:45s} — {reason}")

# %% Compute each foreground activity's own activation scale -- how many
# units of its own internal brightway scale are demanded per 1 unit of the
# functional unit (BatteryUseProxyAct) -- by walking the internal-link edges
# already recorded in db_data, rather than hand-summing raw declared flow
# amounts. A flow's raw amount is stated per 1 unit of *its own* activity's
# scale, not per 1 kg of the overall battery, so activities reached via a
# long internal-link chain (e.g. CellManufacturingAct, several hops from the
# FU) need their own amounts divided down by how much of that activity is
# actually demanded -- exactly what a real brightway solve would do, computed
# here without needing one.
all_activities = {key: meta for db in db_data.values() for key, meta in db.items()}

FU_KEY = next(
    key for uri, key in activity_uri_to_key.items() if uri.split("#")[-1] == "BatteryUseProxyAct"
)

demanded_by = {}
for consumer_key, meta in all_activities.items():
    for exc in meta["exchanges"]:
        if exc["type"] != "technosphere":
            continue
        producer_key = exc["input"]
        if producer_key in all_activities:
            demanded_by.setdefault(producer_key, []).append((consumer_key, exc["amount"]))

def production_amount(key):
    return next(
        exc["amount"] for exc in all_activities[key]["exchanges"] if exc["type"] == "production"
    )


_activity_scale_cache = {}


def activity_scale(key):
    if key in _activity_scale_cache:
        return _activity_scale_cache[key]
    if key == FU_KEY:
        _activity_scale_cache[key] = 1.0
        return 1.0
    # Brightway's own linear solve doesn't just apply each exchange
    # coefficient -- it also divides by the *producer's own* production
    # amount (its diagonal in the technosphere matrix). Skipping that division
    # is invisible wherever production_amount(key) == 1 (nearly every
    # activity here), which is exactly why it went unnoticed until
    # MetalTreatmentAct (production amount 0.577): the 0.577 exchange
    # coefficient pulling it and its own 0.577 production amount cancel
    # exactly, so its real supply equals its consumer's, not 0.577x smaller.
    total = sum(
        activity_scale(consumer_key) * amount for consumer_key, amount in demanded_by.get(key, [])
    )
    total /= production_amount(key)
    _activity_scale_cache[key] = total
    return total


# %% Rescale the manufacturing-stage acquisition flows tracked by a
# CFFScenario elsewhere (see CFF_TRACKED_ACQUISITION_FLOWTYPES), so their
# combined true mass (raw amount x activity_scale of the activity that
# declares them) isn't double counted against the CFF's own acquisition-side
# terms (computed on the fixed, RDF-declared *Waste amount). Since we don't
# know which specific physical portion of each material the CFFScenario
# covers, the covered fraction is suppressed proportionally across every
# manufacturing-stage source of that material -- the least presumptuous
# option without editing the case study to record that mapping explicitly.
cff_waste_amount_by_material = {}
for flow_uri in g.subjects(FLOW.hasCFFScenario, None):
    scenario = g.value(flow_uri, FLOW.hasCFFScenario)
    local = scenario.split("#")[-1]
    if not local.endswith("CFFScenario"):
        continue
    material = local[: -len("CFFScenario")]
    cff_waste_amount_by_material[material] = cff_waste_amount_by_material.get(
        material, 0.0
    ) + (flow_amount(flow_uri) or 0.0)

true_mass_by_material = {}
refs_by_material = {}
for host_key, exc, raw_amount, material in cff_tracked_exchange_refs:
    true_mass = raw_amount * activity_scale(host_key)
    true_mass_by_material[material] = true_mass_by_material.get(material, 0.0) + true_mass
    refs_by_material.setdefault(material, []).append((host_key, exc, raw_amount, true_mass))

print("\nCFF-tracked manufacturing-stage material reconciliation:")
for material, true_mass in true_mass_by_material.items():
    waste_amount = cff_waste_amount_by_material.get(material, 0.0)
    fraction = min(waste_amount / true_mass, 1.0) if true_mass else 0.0
    print(
        f"  {material:10s} true mass={true_mass:10.6g} kg  "
        f"CFF-tracked={waste_amount:10.6g} kg  suppressing {100 * fraction:5.1f}%"
    )
    for host_key, exc, raw_amount, this_true_mass in refs_by_material[material]:
        exc["amount"] *= 1 - fraction

# %% Write every database to Brightway. Run only once the resolution report
# above shows 0 unresolved flows.
#
# Two passes: cross-database exchanges (e.g. PackDataset -> ModuleDataset)
# reference activities that may not exist yet at write time, and
# Database.write() requires every key an exchange points at to already be
# registered in brightway's global mapping. So pass 1 writes every database
# with just its production exchange (registers every activity key across all
# 5 databases), then pass 2 overwrites each with its full exchange list, by
# which point every cross-database reference resolves.
for _, db_name, _ in lci_datasets:
    stub_data = {
        key: {**meta, "exchanges": meta["exchanges"][:1]}
        for key, meta in db_data[db_name].items()
    }
    bw.Database(db_name).write(stub_data)

for _, db_name, _ in lci_datasets:
    db = bw.Database(db_name)
    db.write(db_data[db_name])
    print(f"Wrote database {db_name!r} ({len(db_data[db_name])} activities)")

# %%
# %% The functional unit: 1 kg of "battery use (proxy)", which now pulls in
# both the full production chain (via BatteryLiIonNMC111AtCustomer) and the
# full EoL chain (via EoLBatteryDisassembly) as its two inputs.
fu_act = bw.Database("PackDataset").get("BatteryUseProxyAct")
demand = {fu_act: 1.0}

# battery-pef.ttl's declared functional unit is 1 kWh of battery capacity,
# reached from this 1 kg reference via ps:RFtoFUConversion.
RF_TO_FU = 0.00687583333333

# %% The 16 EF3.1 categories declared in battery-pef.ttl's :Scope, mapped to
# the matching bw2 method tuples (excludes the optional carcinogenic/
# non-carcinogenic organic/inorganic and climate-change sub-splits).
CATEGORY_METHODS = {
    "HumanToxicityCancer": (
        "EF v3.1",
        "human toxicity: carcinogenic",
        "comparative toxic unit for human (CTUh)",
    ),
    "ClimateChange": ("EF v3.1", "climate change", "global warming potential (GWP100)"),
    "EutrophicationFreshwater": (
        "EF v3.1",
        "eutrophication: freshwater",
        "fraction of nutrients reaching freshwater end compartment (P)",
    ),
    "LandUse": ("EF v3.1", "land use", "soil quality index"),
    "ResourceUseMineralsAndMetals": (
        "EF v3.1",
        "material resources: metals/minerals",
        "abiotic depletion potential (ADP): elements (ultimate reserves)",
    ),
    "OzoneDepletion": ("EF v3.1", "ozone depletion", "ozone depletion potential (ODP)"),
    "Acidification": ("EF v3.1", "acidification", "accumulated exceedance (AE)"),
    "IonisingRadiationHumanHealth": (
        "EF v3.1",
        "ionising radiation: human health",
        "human exposure efficiency relative to u235",
    ),
    "HumanToxicityNonCancer": (
        "EF v3.1",
        "human toxicity: non-carcinogenic",
        "comparative toxic unit for human (CTUh)",
    ),
    "EutrophicationTerrestrial": (
        "EF v3.1",
        "eutrophication: terrestrial",
        "accumulated exceedance (AE)",
    ),
    "ParticulateMatter": (
        "EF v3.1",
        "particulate matter formation",
        "impact on human health",
    ),
    "EutrophicationMarine": (
        "EF v3.1",
        "eutrophication: marine",
        "fraction of nutrients reaching marine end compartment (N)",
    ),
    "EcoToxicityFreshwater": (
        "EF v3.1",
        "ecotoxicity: freshwater",
        "comparative toxic unit for ecosystems (CTUe)",
    ),
    "ResourceUseFossils": (
        "EF v3.1",
        "energy resources: non-renewable",
        "abiotic depletion potential (ADP): fossil fuels",
    ),
    "WaterUse": (
        "EF v3.1",
        "water use",
        "user deprivation potential (deprivation-weighted water consumption)",
    ),
    "PhotochemicalOzoneFormationHumanHealth": (
        "EF v3.1",
        "photochemical oxidant formation: human health",
        "tropospheric ozone concentration increase",
    ),
}

# %% Run all 16 EF3.1 categories at once
# %% Run all 16
print(f"{'efic: category':45s} {'per 1 kg use':>14s} {'per 1 kWh FU':>14s}")
results = {}
for name, method in CATEGORY_METHODS.items():
    if method not in bw.methods:
        continue
    lca = bw.LCA(demand, method)
    lca.lci()
    lca.lcia()
    results[name] = lca.score
    print(f"{name:45s} {lca.score:14.4g} {lca.score * RF_TO_FU:14.4g}")
## %% Top contributors for climate change, as a sanity check
from bw2analyzer import ContributionAnalysis

lca = bw.LCA(demand, CATEGORY_METHODS["ClimateChange"])
lca.lci()
lca.lcia()
ca = ContributionAnalysis()
print(f"\nTop contributors for climate change:")
for score, amount, act in ca.annotated_top_processes(lca, limit=15):
    print(f"  {score:12.4g}  {act['name']} ({act['database']})")

# %% Contribution per PEF life cycle stage, using battery-pef.ttl's
# prs:ActivityLink (prs:forActivity / prs:hasLifeCycleStage).
#
# Per-activity DIRECT contribution (each activity's own biosphere exchanges,
# scaled by brightway's solved system-wide demand for it) is what
# ContributionAnalysis works from, and summing it over every activity in the
# system exactly equals lca.score with no double counting -- brightway solves
# the whole technosphere as one linear system, so this is a true partition.
#
# Caveat: only the 15 foreground activities carry an ActivityLink/stage tag.
# Everything upstream in ecoinvent (the vast majority of most LCIA scores)
# falls into "Background (ecoinvent)" below rather than being folded into the
# stage that actually pulled it in. Ask if you want that resolved with a
# proper cut-at-foreground-boundary (cumulative, non-double-counting)
# attribution instead -- that needs walking the solved supply chain, not just
# this direct per-activity split.
PRS = Namespace("https://w3id.org/mintjesba/pefdpp/product-system#")

activity_to_stage = {}
for al in g.subjects(RDF.type, PRS.ActivityLink):
    act_uri = g.value(al, PRS.forActivity)
    stage = g.value(al, PRS.hasLifeCycleStage)
    if act_uri is not None and stage is not None:
        activity_to_stage[act_uri] = stage.split("#")[-1]

key_to_stage = {
    activity_uri_to_key[act_uri]: stage
    for act_uri, stage in activity_to_stage.items()
    if act_uri in activity_uri_to_key
}
# The synthetic CFF acquisition pseudo-activities (see cff_acquisition_key in
# Step 2) aren't declared in the RDF case study, so they carry no
# ActivityLink -- tag them here instead, purely as an implementation detail.
for wrapper_key in wrapper_exchange_contributions:
    key_to_stage[wrapper_key] = SYNTHETIC_ACQUISITION_STAGE
print(f"{len(key_to_stage)} of {len(activity_to_stage)} ActivityLink activities found in brightway")

lca = bw.LCA(demand, CATEGORY_METHODS["ClimateChange"])
lca.lci()
lca.lcia()

from collections import defaultdict

stage_totals = defaultdict(float)
for score, amount, act in ca.annotated_top_processes(lca, limit=len(lca.activity_dict)):
    stage = key_to_stage.get(act.key, "Background (ecoinvent)")
    stage_totals[stage] += score

print(f"\nContribution per life cycle stage ({CATEGORY_METHODS['ClimateChange'][-1]}):")
for stage, score in sorted(stage_totals.items(), key=lambda kv: -abs(kv[1])):
    print(f"  {stage:30s} {score:14.4g}  ({100 * score / lca.score:5.1f}%)")
print(f"  {'TOTAL':30s} {lca.score:14.4g}")

# %% Marginal (cut-at-foreground-boundary) contribution per life cycle stage.
#
# For each of the 15 ActivityLink-tagged activities, computes the cumulative
# (fully recursive) impact of the amount brightway actually solved for it,
# then subtracts the cumulative impact already attributed to any OTHER
# tagged activity it directly consumes. What's left is that activity's own
# direct emissions plus everything upstream that ISN'T inside another tagged
# activity's subtree -- so every ecoinvent background contribution gets
# folded into whichever foreground activity actually pulled it in, instead of
# sitting in an undifferentiated "Background" bucket. By linearity of the
# technosphere solve this is an exact decomposition: marginal scores sum to
# the total with no double counting (checked below).
#
# redo_lci() reuses the technosphere matrix already factorized for `demand`
# instead of rebuilding/re-factorizing it per activity (~30 solves here
# across 15 activities + their internal links -- fast with reuse, slow
# without).
def stage_contributions(method, demand=demand):
    lca = bw.LCA(demand, method)
    lca.lci(factorize=True)
    lca.lcia()
    total_score = lca.score
    supply = {key: lca.supply_array[col] for key, col in lca.activity_dict.items()}

    def cumulative_score(key, amount):
        lca.redo_lci({key: amount})
        lca.lcia()
        return lca.score

    _production_amount_cache = {}

    def production_amount(key):
        if key not in _production_amount_cache:
            db_name, code = key
            exc = next(iter(bw.Database(db_name).get(code).production()))
            _production_amount_cache[key] = exc["amount"]
        return _production_amount_cache[key]

    # Some ActivityLink-tagged activities may not be reachable from the
    # demand yet (e.g. BrazingServiceAct/NocolokAct, currently orphaned --
    # nothing in the product system consumes their output). Skip them rather
    # than crashing on a missing supply-array entry; the residual check below
    # will then reflect their un-attributed contribution (0, since nothing
    # demands them) rather than silently pretending they don't matter once
    # they're actually wired in.
    unreachable = [key for key in key_to_stage if key not in supply]
    if unreachable:
        print(f"Skipping {len(unreachable)} unreachable ActivityLink activities:")
        for key in unreachable:
            print(f"  {key}")

    marginal = {}
    for key in key_to_stage:
        if key in unreachable:
            continue
        db_name, code = key
        act = bw.Database(db_name).get(code)
        score = cumulative_score(key, supply[key])
        for exc in act.technosphere():
            child_key = exc.input.key
            if child_key in key_to_stage and child_key not in unreachable:
                # exc["amount"] * supply[key] is the raw exchange signal, not
                # the child's actual attributable supply -- brightway's own
                # solve also divides by the *child's* own production amount
                # (its diagonal in the technosphere matrix). Skipping that
                # division under-subtracts whenever the child's production
                # amount isn't 1 (only MetalTreatmentAct, at 0.577, in this
                # case study), silently double counting part of its
                # contribution between its parent's bucket and its own.
                child_amount = exc["amount"] * supply[key] / production_amount(child_key)
                score -= cumulative_score(child_key, child_amount)
        marginal[key] = score

    stage_totals = defaultdict(float)
    for key, score in marginal.items():
        stage_totals[key_to_stage[key]] += score

    residual = total_score - sum(stage_totals.values())
    print(
        f"Unattributed residual (should be ~0): {residual:.4g} "
        f"({100 * residual / total_score:.3f}% of total)"
    )
    return stage_totals, total_score


stage_totals, total_score = stage_contributions(CATEGORY_METHODS["ClimateChange"])
print(f"\nMarginal contribution per life cycle stage ({CATEGORY_METHODS['ClimateChange'][-1]}):")
for stage, score in sorted(stage_totals.items(), key=lambda kv: -abs(kv[1])):
    print(f"  {stage:30s} {score:14.4g}  ({100 * score / total_score:5.1f}%)")
print(f"  {'TOTAL':30s} {total_score:14.4g}")

# %%
