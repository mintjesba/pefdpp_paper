from pathlib import Path
from rdflib import Graph, RDF, OWL, RDFS, Namespace, URIRef, Literal

SKIP = {"ef31-elementaryflows.ttl"}

def parse_file(path):
    g = Graph()
    try:
        g.parse(str(path), format="turtle")
        return g, None
    except Exception as e:
        return None, str(e)

ttl_files = sorted([p for p in Path("ontology").rglob("*.ttl") if p.name not in SKIP])
errors = []
combined = Graph()
file_graphs = {}
for f in ttl_files:
    g, err = parse_file(f)
    if err:
        errors.append((str(f), err))
        print(f"FAIL  {f}\n      {err}")
    else:
        combined += g
        file_graphs[str(f)] = g

print(f"Parse: {len(ttl_files)-len(errors)}/{len(ttl_files)} OK\n")
if errors:
    import sys; sys.exit(1)

PEFDPP = Namespace("https://w3id.org/pefdpp/")
LCIA   = Namespace("https://w3id.org/pefdpp/lcia#")
PS     = Namespace("https://w3id.org/pefdpp/pefstudy#")
PRS    = Namespace("https://w3id.org/pefdpp/product-system#")
EFU    = Namespace("https://w3id.org/pefdpp/ef31-units#")
FLOW   = Namespace("https://w3id.org/pefdpp/flow#")
ACT    = Namespace("https://w3id.org/pefdpp/activity#")
DS     = Namespace("https://w3id.org/pefdpp/dataset#")
DQ     = Namespace("https://w3id.org/pefdpp/dataquality#")
OM     = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")

issues = []
def sec(t):  issues.append(f"\n=== {t} ===")
def ok(m):   issues.append(f"  OK   {m}")
def warn(m): issues.append(f"  WARN {m}")
def err(m):  issues.append(f"  ERR  {m}")

# 1. Undeclared pefdpp: properties
sec("1. Undeclared PEFDPP properties")
prop_types = {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, RDF.Property}
declared_props = set()
for pt in prop_types:
    declared_props |= set(combined.subjects(RDF.type, pt))
pefdpp_ns = str(PEFDPP)
undeclared = {p for s, p, o in combined
              if str(p).startswith(pefdpp_ns) and p not in declared_props}
if undeclared:
    for p in sorted(str(x) for x in undeclared):
        err(p.split("#")[-1])
else:
    ok("All used pefdpp: properties are declared")

# 2. Undeclared classes used as rdf:type
sec("2. Undeclared PEFDPP classes used as rdf:type")
declared_classes = set(combined.subjects(RDF.type, OWL.Class)) | \
                   set(combined.subjects(RDF.type, RDFS.Class))
used_classes = {o for s, p, o in combined.triples((None, RDF.type, None))
                if isinstance(o, URIRef) and str(o).startswith(pefdpp_ns)}
undeclared_classes = used_classes - declared_classes
if undeclared_classes:
    for c in sorted(str(x) for x in undeclared_classes):
        err(c.split("#")[-1])
else:
    ok("All used pefdpp: classes are declared")

# 3. PEFRequired properties on PEFStudy instances
sec("3. PEFRequired properties on PEFStudy instances")
pef_required_props = {p for p in declared_props
                      if (p, PEFDPP.PEFRequired, Literal(True)) in combined}
studies = list(combined.subjects(RDF.type, PS.PEFStudy))
if not studies:
    warn("No ps:PEFStudy instances found")
for study in studies:
    study_props = {p for s, p, o in combined.triples((study, None, None))}
    for rp in pef_required_props:
        domain = list(combined.objects(rp, RDFS.domain))
        if PS.PEFStudy in domain and rp not in study_props:
            err(f"{study.split('#')[-1]} missing required: {rp.split('#')[-1]}")
    ok(f"{study.split('#')[-1]} checked ({len(study_props)} props)")

# 4. ImpactCategory completeness
sec("4. lcia:ImpactCategory completeness")
ics = list(combined.subjects(RDF.type, LCIA.ImpactCategory))
missing_method = [ic for ic in ics if not list(combined.objects(ic, LCIA.calculatedByMethod))]
missing_unit   = [ic for ic in ics if not list(combined.objects(ic, LCIA.hasIndicatorUnit))]
if missing_method:
    for ic in sorted(str(x) for x in missing_method):
        err(f"No calculatedByMethod: {ic.split('#')[-1]}")
if missing_unit:
    for ic in sorted(str(x) for x in missing_unit):
        err(f"No hasIndicatorUnit: {ic.split('#')[-1]}")
if not missing_method and not missing_unit:
    ok(f"All {len(ics)} ImpactCategories have method + unit")

# 5. LCIAResult forImpactCategory resolution
sec("5. LCIAResult forImpactCategory resolution")
results = list(combined.subjects(RDF.type, LCIA.LCIAResult))
dangling = []
for r in results:
    for ic in combined.objects(r, LCIA.forImpactCategory):
        if (ic, RDF.type, LCIA.ImpactCategory) not in combined:
            dangling.append((r, ic))
if dangling:
    for r, ic in dangling:
        err(f"{r.split('#')[-1]} -> {ic.split('#')[-1]} not typed as ImpactCategory")
else:
    ok(f"All {len(results)} LCIAResults point to valid ImpactCategories")

# 6. ActivityLink forActivity resolution
sec("6. ActivityLink forActivity resolution")
links = list(combined.subjects(RDF.type, PRS.ActivityLink))
missing_act = []
for lnk in links:
    for act in combined.objects(lnk, PRS.forActivity):
        if (act, RDF.type, ACT.Activity) not in combined:
            missing_act.append((lnk, act))
if missing_act:
    for lnk, act in missing_act:
        err(f"{lnk.split('#')[-1]} -> {act.split('#')[-1]} not typed as act:Activity")
else:
    ok(f"All {len(links)} ActivityLinks resolve to typed Activities")

# 7. FlowType sourcedFrom completeness
sec("7. FlowType sourcedFrom completeness")
flow_classes = {FLOW.ProductFlow, FLOW.WasteFlow, FLOW.ElementaryFlow}
flow_types = set()
for fc in flow_classes:
    flow_types |= set(combined.subjects(RDF.type, fc))
missing_src = [ft for ft in flow_types
               if not list(combined.objects(ft, FLOW.sourcedFrom))]
if missing_src:
    for ft in sorted(str(x) for x in missing_src):
        err(f"No sourcedFrom: {ft.split('#')[-1]}")
else:
    ok(f"All {len(flow_types)} FlowTypes have sourcedFrom")

# 8. Flow hasFlowType targets are typed
sec("8. Flow hasFlowType resolution")
has_ft = FLOW.hasFlowType
dangling_ft = []
flow_type_classes = {FLOW.ProductFlow, FLOW.WasteFlow, FLOW.ElementaryFlow, FLOW.FlowType}
for flow_ind in combined.subjects(has_ft, None):
    for ft in combined.objects(flow_ind, has_ft):
        types_of_ft = set(combined.objects(ft, RDF.type))
        if not types_of_ft & flow_type_classes:
            dangling_ft.append((flow_ind, ft))
if dangling_ft:
    for fi, ft in sorted(dangling_ft, key=lambda x: str(x[1])):
        err(f"hasFlowType -> {ft.split('#')[-1]} has no flow type class")
else:
    fcount = len(list(combined.subjects(has_ft, None)))
    ok(f"All hasFlowType references resolve ({fcount} flow individuals checked)")

# 9. CFF parameter values in [0,1]
sec("9. CFF parameter value sanity (rates/fractions in 0-1)")
cff_props = [FLOW.A, FLOW.B, FLOW.Qsin, FLOW.Qsout, FLOW.Qp, FLOW.R1, FLOW.R2, FLOW.R3]
out_of_range = []
for prop in cff_props:
    for s, p, o in combined.triples((None, prop, None)):
        try:
            v = float(o)
            if not (0.0 <= v <= 1.0):
                out_of_range.append((s, prop, v))
        except Exception:
            pass
if out_of_range:
    for s, p, v in out_of_range:
        warn(f"{s.split('#')[-1]}.{p.split('#')[-1]} = {v} (outside 0-1)")
else:
    ok("All CFF rate/fraction values in [0, 1]")

# 10. om:Measure completeness
sec("10. om:Measure completeness")
measures = list(combined.subjects(RDF.type, OM.Measure))
missing_val  = [m for m in measures if not list(combined.objects(m, OM.hasNumericalValue))]
missing_unit = [m for m in measures if not list(combined.objects(m, OM.hasUnit))]
if missing_val:
    warn(f"{len(missing_val)} om:Measure(s) missing hasNumericalValue")
if missing_unit:
    warn(f"{len(missing_unit)} om:Measure(s) missing hasUnit")
if not missing_val and not missing_unit:
    ok(f"All {len(measures)} om:Measures have value + unit")

# 11. DataQuality completeness
sec("11. DataQuality completeness")
dq_blocks = list(combined.subjects(RDF.type, DQ.DataQuality))
missing_dqr = [d for d in dq_blocks if not list(combined.objects(d, DQ.hasOverallDQR))]
missing_crit = [d for d in dq_blocks if not list(combined.objects(d, DQ.hasDQRCriterion))]
if missing_dqr:
    warn(f"{len(missing_dqr)} DataQuality block(s) missing hasOverallDQR")
if missing_crit:
    warn(f"{len(missing_crit)} DataQuality block(s) missing hasDQRCriterion")
if not missing_dqr and not missing_crit:
    ok(f"All {len(dq_blocks)} DataQuality blocks have DQR + criteria")

# 12. DQRCriterion completeness
sec("12. DQRCriterion completeness")
criteria = list(combined.subjects(RDF.type, DQ.DQRCriterion))
missing_dim = [c for c in criteria if not list(combined.objects(c, DQ.forDimension))]
missing_val2 = [c for c in criteria if not list(combined.objects(c, DQ.hasValue))]
if missing_dim:
    warn(f"{len(missing_dim)} DQRCriterion(s) missing forDimension")
if missing_val2:
    warn(f"{len(missing_val2)} DQRCriterion(s) missing hasValue")
if not missing_dim and not missing_val2:
    ok(f"All {len(criteria)} DQRCriteria have dimension + value")

# 13. Scope includesImpactCategory matches hasLCIAResult categories
sec("13. Scope includesImpactCategory vs BatteryPackPEFStudy LCIA coverage")
for study in studies:
    scopes = list(combined.objects(study, PS.hasScope))
    for scope in scopes:
        scope_ics = set(combined.objects(scope, PS.includesImpactCategory))
        result_ics = set()
        for r in combined.objects(study, PS.hasLCIAResult):
            for ic in combined.objects(r, LCIA.forImpactCategory):
                result_ics.add(ic)
        in_scope_not_result = scope_ics - result_ics
        in_result_not_scope = result_ics - scope_ics
        if in_scope_not_result:
            for ic in sorted(str(x) for x in in_scope_not_result):
                warn(f"In scope but no LCIA result: {ic.split('#')[-1]}")
        if in_result_not_scope:
            for ic in sorted(str(x) for x in in_result_not_scope):
                warn(f"Has LCIA result but not in scope: {ic.split('#')[-1]}")
        if not in_scope_not_result and not in_result_not_scope:
            ok(f"Scope ICs match LCIA results ({len(scope_ics)} categories)")

# 14. Ontology declarations
sec("14. owl:Ontology declaration in every TTL file")
missing_ont = []
for fpath, fg in file_graphs.items():
    if not list(fg.subjects(RDF.type, OWL.Ontology)):
        missing_ont.append(Path(fpath).name)
if missing_ont:
    for f in missing_ont: warn(f"No owl:Ontology declaration: {f}")
else:
    ok(f"All {len(file_graphs)} files have owl:Ontology declaration")

# 15. LCIDatasets have a title
sec("15. LCIDataset metadata")
datasets = list(combined.subjects(RDF.type, DS.LCIDataset))
from rdflib.namespace import DCTERMS
missing_title = [d for d in datasets if not list(combined.objects(d, DCTERMS.title))]
if missing_title:
    for d in sorted(str(x) for x in missing_title):
        warn(f"LCIDataset without dcterms:title: {d.split('#')[-1]}")
else:
    ok(f"All {len(datasets)} LCIDatasets have a title")

print("\n".join(issues))
err_count  = sum(1 for l in issues if l.strip().startswith("ERR"))
warn_count = sum(1 for l in issues if l.strip().startswith("WARN"))
print(f"\nResult: {err_count} error(s), {warn_count} warning(s) | {len(combined)} triples total")
