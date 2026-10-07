# PEFDPP ontology and battery case study

This repository contains the **PEFDPP ontology**, an OWL 2 DL ontology for encoding Product Environmental Footprint (PEF)-compliant life cycle assessment data in Digital Product Passports (DPPs), together with the **Li-ion battery case study** used to demonstrate it. It accompanies the article:

> Mintjes, B., Barilli, F., Mondello, A., van Nielen, S., Hischier, R., Donati, F., Mogollón, J.M. *Integrating Product Environmental Footprint and Digital Product Passports: A Data Model for Traceable, Reusable Environmental Performance Information.* Journal of Circular Economy.

Ontology version: **1.0.0**. Namespace: `https://w3id.org/pefdpp/`

Note: the namespace does not resolve yet, and the ontology files should be loaded separately.

## Contents

```
ontology/
  ontology/
    pefdpp.ttl                  Top-level ontology; imports all PEFDPP modules
    dataquality.ttl             Data quality (DQR criteria and ratings)
    ilcdname.ttl                ILCD naming conventions for activities and flows
    lci/
      flow.ttl                  Product, waste and elementary flows; CFF parameters and EoL scenarios
      activity.ttl              Activities (unit processes)
      dataset.ttl               LCI datasets and EF compliance levels
    pefstudy/
      lcia.ttl                  LCIA methods, impact categories and results
      product-system.ttl        Product systems, activity links and life cycle stages
      pefstudy.ttl              Goal, scope, functional unit and system boundary of a PEF study
    ef/                         EF 3.1 units, impact indicators and LCIA methods
    skos/                       SKOS vocabularies: EF 3.1 elementary flows and impact
                                categories, PEF geographies, additional-information topics
case-study/
  lcidatasets/
    dpp/                        Foreground LCI datasets as they would be carried in DPPs
                                (battery pack, module, cell, brazing)
    secondary/                  References to secondary data: ecoinvent activities,
                                EF 3.1 biosphere flows, battery end-of-life
  battery-pef.ttl               The PEF study instance (goal, scope, product system, LCIA results)
  calculations/
    project-setup.py            Builds the product system in Brightway and calculates the LCIA results
environment.yml                 Conda environment for the case-study calculation
```

## Using the ontology

The Turtle files can be opened in any RDF/OWL tool (e.g. Protégé) or loaded with a library such as `rdflib`. Load `ontology/ontology/pefdpp.ttl` together with the module files. Its `owl:imports` refer to the w3id IRIs of the modules, which correspond to the files in `ontology/ontology/`.

`skos/ef31-elementaryflows.ttl` is large (about 42 MB) because it contains the complete EF 3.1 elementary flow list.

## Reproducing the case study

The case study is an NMC111 Li-ion electric vehicle battery pack, following the Rules for the Calculation of the Carbon Footprint of Electric Vehicle Batteries (CFB-EV). The foreground inventory is adapted from Crenna et al. (2021), *Resources, Conservation and Recycling* 170, 105619, https://doi.org/10.1016/j.resconrec.2021.105619. The production sites are fictional.

`case-study/calculations/project-setup.py` reads the ontology and case-study files and resolves the secondary-data references against ecoinvent and biosphere3. It then writes the foreground datasets as Brightway databases and calculates the EF 3.1 impact results reported in `battery-pef.ttl`.

**Requirements**

- A licence for **ecoinvent 3.12** (cut-off system model). The ecoinvent data are not included in this repository. The case-study files only reference ecoinvent activities by name, location and UUID.
- A Brightway 2 project named `ecoinvent312`, containing the databases `ecoinvent-3.12-cutoff` and `biosphere3` and the `EF v3.1` LCIA methods.
- The conda environment in `environment.yml`:

```
conda env create -f environment.yml
conda activate pefdpp-case-study
python case-study/calculations/project-setup.py
```

The script adds the case-study foreground databases to the `ecoinvent312` project and prints the LCIA results and the contribution analysis.

## Third-party content

- The EF 3.1 vocabularies in `ontology/ontology/ef/` and `ontology/ontology/skos/ef31-*` are derived from the Environmental Footprint 3.1 reference package of the European Commission's Joint Research Centre (https://eplca.jrc.ec.europa.eu/). They are reused under the Commission's reuse policy (Decision 2011/833/EU).
- ecoinvent activity names and UUIDs are cited as required by the ecoinvent licence: ecoinvent Association, ecoinvent database version 3.12, cut-off system model.

## Licence

- Ontology and case-study data (`*.ttl`): [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
- Code (`case-study/calculations/project-setup.py`): MIT licence

See [LICENSE](LICENSE).

## How to cite

Please cite the article above when using this ontology.

## Funding

This work was funded by the European Union's Horizon Europe programme under grant agreements No. 101092281 (CE-RISE) and No. 101178719 (Lasers4MaaS).

## Contact

Berend Mintjes, Institute of Environmental Sciences (CML), Leiden University. Email: b.a.mintjes@cml.leidenuniv.nl, ORCID: [0009-0008-3997-4351](https://orcid.org/0009-0008-3997-4351)
