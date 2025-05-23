"""
This file is `explore` Jupyter Notebook
"""

if True:  # just to bypass the ruff warning
    print("Please wait")
import math
import os
import sys

from IPython.core.display import Markdown, display

if True:
    sys.stdout = open(os.devnull, "w")
from bw2data.project import projects

if True:
    sys.stdout = sys.__stdout__
import base64
import csv
import io
import json
import os

import bw2analyzer
import bw2calc
import bw2data
import ipywidgets
import pandas
import pandas.io.formats.style
from bw2data.utils import get_activity, get_node

Illustration = open("notebooks/bw2.svg").read()
BIOSPHERE = "biosphere3"
PROJECTS = [p.name for p in bw2data.projects]
EF31 = "Environmental Footprint 3.1 (adapted) patch wtu"
VISITED = []  # visited activities since the last search
LIMIT = 100
IMPACTS = {}
with open("impacts.json") as f:
    IMPACTS = json.load(f)


project = PROJECTS[0] if len(PROJECTS) else None
if project:
    bw2data.projects.set_current(project)
database = list(bw2data.databases)[0] if len(bw2data.databases) else None
methods = sorted({m[0] for m in bw2data.methods})
method = EF31 if EF31 in methods else (methods[0] if len(methods) else None)


# widgets
w_panel = ipywidgets.HTML()
w_project = ipywidgets.Dropdown(
    value=project,
    options=PROJECTS,
    description="PROJECT",
)
w_database = ipywidgets.Dropdown(
    options=list(bw2data.databases), description="DATABASE"
)
w_search = ipywidgets.Text(value="", placeholder="Search string", description="SEARCH")
w_method = ipywidgets.Dropdown(
    value=method,
    options=sorted({m[0] for m in bw2data.methods}),
    description="METHOD",
)
w_limit = ipywidgets.IntText(value=LIMIT, step=1, description="LIMIT")
w_activity = ipywidgets.Dropdown(options=[], description="ACTIVITY")
w_results = ipywidgets.Output(value="Résultat")
w_details = ipywidgets.Output(value="Détails")
w_impact_category = ipywidgets.Dropdown(
    options=[("", "")]
    + [(", ".join(m[1:]), m[1:]) for m in bw2data.methods if m[0] == method],
    description="IMPACT CATEG",
)

display(Markdown("# Brightway explorer :"))


def go_back(button):
    """We clicked on the Back button"""
    linkto(button, append_to_stack=False)


w_back_button = ipywidgets.Button(description="←back")
w_back_button.style.button_color = "white"
w_back_button.layout.display = "none"
setattr(w_back_button, "search", "")
w_back_button.on_click(go_back)


def w_csv_button(contents, columns):
    csvfile = io.StringIO()
    writer = csv.DictWriter(csvfile, fieldnames=columns)
    writer.writeheader()
    for item in contents:
        writer.writerow({k: v for k, v in zip(columns, item)})
    csvfile.seek(0)
    contents = csvfile.read()
    return """
        <a download="{filename}" href="data:text/csv;base64,{payload}" download>
        <button class="p-Widget jupyter-widgets jupyter-button widget-button mod-warning">Download as CSV</button>
        </a>
    """.format(
        payload=base64.b64encode(contents.encode()).decode(), filename="export.csv"
    )


@w_results.capture()
def display_results(database, search, limit):
    """display the list of search results in the w_results widget"""
    results = list(bw2data.Database(database).search(search, limit=limit))
    for a in results:
        a["categories"] = ", ".join(a.get("categories", []))
    w_results.clear_output()
    w_details.clear_output()
    w_activity.options = [("", "")] + [
        (
            str(i) + f" {a.get('name', '')} "
            f"{('(in ' + a.get('categories', []) + ')') if a.get('categories') else ''}",
            a,
        )
        for i, a in enumerate(results)
    ]
    if len(results) == 0:
        display(Markdown("(No results)"))
    else:
        display(
            Markdown(
                f"## {('+' if len(results) == LIMIT else '')}{len(results)} results"
            )
        )
        columns = ["name", "categories", "code", "location"]
        html = pandas.io.formats.style.Styler(
            pandas.DataFrame(results, columns=columns)
        )
        html.set_properties(**{"background-color": "#EEE"})
        display(
            ipywidgets.HTML(
                w_csv_button(
                    [tuple(item[k] for k in columns if k in item) for item in results],
                    columns,
                )
            )
        )
        display(ipywidgets.HTML(html.to_html()))


@w_results.capture()
def display_characterization_factors(method, impact_category):
    w_details.clear_output()
    w_results.clear_output()
    grouped = {}
    for line in bw2data.Method((method,) + impact_category).load() if method else []:
        substance = line[0]
        cf_value = line[1]
        grouped.setdefault(substance, []).append(cf_value)

    rows = []
    for substance, values in grouped.items():
        display_str = ("Multiple values: " if len(values) > 1 else "") + " | ".join(
            str(v) for v in values
        )
        avg_value = sum(values) / len(values)
        unit = bw2data.methods[(method,) + impact_category]["unit"]
        rows.append((substance, get_node(id=substance), display_str, unit, avg_value))

    rows_sorted = sorted(rows, key=lambda row: row[4], reverse=True)

    df = pandas.DataFrame(
        [row[:4] for row in rows_sorted],
        columns=["id", "Flow", "amount", "unit"],
    )
    cfs = pandas.io.formats.style.Styler(df)
    cfs.set_properties(**{"background-color": "#EEE"})

    display(
        Markdown(
            f"# {len(cfs.data)} Characterization factors for <b>{', '.join(impact_category)}</b> in {method}"
        )
    )
    if len(cfs.data):
        display(ipywidgets.HTML(cfs.to_html()))


def linkto(button, append_to_stack=True):
    """We clicked on an activity button to visit"""

    if append_to_stack:
        VISITED.append((button.database, button.search))
    else:
        if len(VISITED) > 1:
            VISITED.pop()
        elif len(VISITED) == 1:
            w_search.value = VISITED.pop()
    setattr(w_back_button, "database", VISITED[-1][0] if len(VISITED) > 0 else "")
    setattr(w_back_button, "search", VISITED[-1][1] if len(VISITED) > 0 else "")
    results = list(
        bw2data.Database(button.database).search(button.search, limit=w_limit.value)
    )
    if len(VISITED) == 0:
        w_search.value = ""
    w_activity.value = None
    w_activity.options = [
        (str(i) + " " + a.get("name", ""), a) for i, a in enumerate(results)
    ]
    w_activity.value = results[0] if len(results) > 0 else None


def lookup_cf(loaded_method, element):
    """Find a Characterization Factor by name in the list of already loaded CFs"""
    cfs = [cf for cf in loaded_method if cf[0] == element]
    if len(cfs) == 0:
        return "Ø"
    elif len(cfs) == 1:
        return "{:.4g}".format(cfs[0][1])
    else:
        return "Multiple CFs : " + " | ".join([str(cf[1]) for cf in cfs])


def strepl(s):
    return str(s).replace("\n", "<br/>")


def dict2html(d):
    """Display a dict in HTML"""
    return (
        "<ul>"
        + "".join(
            [
                f"<li><b>{k}</b>: {dict2html(v) if isinstance(v, dict) else list2html(v) if isinstance(v, (list, tuple)) else strepl(v)}</li>"
                for k, v in d.items()
            ]
        )
        + "</ul>"
    )


def list2html(lst):
    """Display a list in HTML"""
    return (
        "<ul>"
        + "".join(
            [
                f"<li><b>{list2html(i) if isinstance(i, (list, tuple)) else dict2html(i) if isinstance(i, dict) else strepl(i)}</b></li>"
                for i in lst
            ]
        )
        + "</ul>"
    )


def changed_project(_):
    project = w_project.value
    database = w_database.value
    search = w_search.value
    limit = w_limit.value
    method = w_method.value
    impact_category = w_impact_category.value
    activity = w_activity.value

    projects.set_current(project)
    # projects.activate_project(project)
    databases = list(bw2data.databases)
    methods = sorted({m[0] for m in bw2data.methods})
    impact_categories = [
        (", ".join(m[1:]), m[1:]) for m in bw2data.methods if m[0] == method
    ]

    # default database
    w_database.value = None
    w_database.options = databases
    if EF31 in methods:
        w_method.options = methods
        method = w_method.value = method if method in methods else EF31
    else:
        w_method.value = None
        w_impact_category.value = None
        w_method.options = methods
        method = w_method.value = method if method in methods else None
    w_impact_category.options = [("", "")] + sorted(
        [(", ".join(m[1:]), m[1:]) for m in bw2data.methods if m[0] == method]
    )
    impact_category = w_impact_category.value = (
        impact_category if impact_category in impact_categories else None
    )
    activity = w_activity.value = None
    display_all(database, search, limit, method, impact_category, activity)


def changed_database(_):
    w_activity.value = None
    display_all(
        w_database.value,
        w_search.value,
        w_limit.value,
        w_method.value,
        w_impact_category.value,
        w_activity.value,
    )


def changed_search(_):
    global VISITED  # 🤮
    database = w_database.value
    search = w_search.value
    limit = w_limit.value
    method = w_method.value
    impact_category = w_impact_category.value
    activity = w_activity.value

    if search:
        if len(VISITED) <= 1:
            VISITED = [(database, search)]
            activity = w_activity.value = None
        else:
            VISITED = []
    display_all(database, search, limit, method, impact_category, activity)


def changed_limit(_):
    database = w_database.value
    search = w_search.value
    limit = w_limit.value
    method = w_method.value
    impact_category = w_impact_category.value
    activity = w_activity.value
    display_all(database, search, limit, method, impact_category, activity)


def changed_method(_):
    database = w_database.value
    search = w_search.value
    limit = w_limit.value
    method = w_method.value
    impact_category = w_impact_category.value
    activity = w_activity.value
    impact_categories = [m[1:] for m in bw2data.methods if m[0] == method]
    w_impact_category.value = None
    w_impact_category.options = [("", None)] + [
        (", ".join(i), i) for i in impact_categories
    ]
    impact_category = w_impact_category.value = (
        impact_category if impact_category in impact_categories else None
    )
    display_all(database, search, limit, method, impact_category, activity)


def changed_impact_category(_):
    database = w_database.value
    search = w_search.value
    limit = w_limit.value
    method = w_method.value
    impact_category = w_impact_category.value
    activity = w_activity.value
    display_all(database, search, limit, method, impact_category, activity)


def changed_activity(_):
    database = w_database.value
    search = w_search.value
    limit = w_limit.value
    method = w_method.value
    impact_category = w_impact_category.value
    activity = w_activity.value
    display_all(database, search, limit, method, impact_category, activity)


def display_all(database, search, limit, method, impact_category, activity):
    if method and impact_category and not search and not activity:
        return display_characterization_factors(method, impact_category)
    elif database and method and activity:
        display_right_panel(database)
        return display_main_data(method, impact_category, activity)
    elif database and search and limit:
        return display_results(database, search, limit)
    else:
        w_details.clear_output()
        w_results.clear_output()


def display_right_panel(database):
    # right panel
    biosphere_name = bw2data.preferences.get("biosphere_database", "")
    biosphere = bw2data.Database(biosphere_name) if biosphere_name else ()
    breadcrumb = [
        # v[0] is the db name, v[1] is the search string
        f"<li>{v[0]} : {bw2data.Database(v[0]).search(v[1])[0] if bw2data.Database(database).search(v[1]) and str(v[1]).startswith('code:') else v[1]}</li>"
        for v in VISITED
    ]
    w_panel.value = (
        f"<div><b>database size</b>: {len(bw2data.Database(database))}</div>"
        f"<div><b>biosphere name</b>: {biosphere_name}</div>"
        f"<div><b>biosphere size</b>: {len(biosphere)}</div>"
        f"{('<ul>⛏️  Breadcrumb: ' + ''.join(breadcrumb)) if len(breadcrumb) > 1 else ''}"
    )
    w_back_button.layout.display = "none" if len(VISITED) <= 1 else "block"


@w_details.capture()
def display_main_data(method, impact_category, activity):
    w_details.clear_output()
    w_results.clear_output()
    display(Markdown("## (Computing impacts...)"))

    # IMPACTS
    scores = dict()
    try:
        lca = bw2calc.LCA({activity: 1})
        impacts_error = ""
        lca.lci()
        for m in [m for m in bw2data.methods if m[0] == method]:
            lca.switch_method(m)
            lca.lcia()
            name = ", ".join(m[1:])
            scores[name] = {
                "Indicateur": name,
                "Score": lca.score,
                "Unité": bw2data.methods[m].get("unit", "(no unit)"),
            }

    except Exception as e:
        impacts_error = (
            "Could not compute impact. Maybe you selected the biosphere?<br/>" + str(e)
        )
    if scores and method == EF31:
        scores["Ecotoxicity, freshwater - organics"] = {
            "Indicateur": "Ecotoxicity, freshwater - organics",
            "Score": scores["Ecotoxicity, freshwater - organics - p.1"]["Score"]
            + scores["Ecotoxicity, freshwater - organics - p.2"]["Score"],
            "Unité": scores["Ecotoxicity, freshwater - organics - p.1"]["Unité"],
        }
        scores["Ecotoxicity, freshwater"] = {
            "Indicateur": "Ecotoxicity, freshwater",
            "Score": scores["Ecotoxicity, freshwater - part 1"]["Score"]
            + scores["Ecotoxicity, freshwater - part 2"]["Score"],
            "Unité": scores["Ecotoxicity, freshwater - part 1"]["Unité"],
        }
        for trigram in [
            t
            for t in IMPACTS.keys()
            if t not in ("ecs", "pef", "htn-c", "etf-c", "htc-c")
        ]:
            scores[IMPACTS[trigram]["label_en"]]["µPt PEF"] = (
                scores[IMPACTS[trigram]["label_en"]]["Score"]
                / IMPACTS[trigram].get("pef", {}).get("normalization", 1)
                * IMPACTS[trigram].get("pef", {}).get("weighting", 0)
                * 1e6
            )
            scores[IMPACTS[trigram]["label_en"]]["Ecoscore"] = (
                scores[IMPACTS[trigram]["label_en"]]["Score"]
                / (IMPACTS[trigram].get("ecoscore", {}) or {}).get("normalization", 1)
                * (IMPACTS[trigram].get("ecoscore", {}) or {}).get("weighting", 0)
                * 1e6
            )
        scores["Ecotoxicity, freshwater, corrected"] = {
            "Indicateur": "Ecotoxicity, freshwater, corrected",
            "Score": IMPACTS["etf-c"]["correction"][0]["weighting"]
            * scores["Ecotoxicity, freshwater - organics"]["Score"]
            + IMPACTS["etf-c"]["correction"][1]["weighting"]
            * scores["Ecotoxicity, freshwater - inorganics"]["Score"],
            "Unité": scores["Ecotoxicity, freshwater"]["Unité"],
        }
        scores["Ecotoxicity, freshwater, corrected"]["Ecoscore"] = (
            scores["Ecotoxicity, freshwater, corrected"]["Score"]
            / IMPACTS["etf-c"]["ecoscore"]["normalization"]
            * IMPACTS["etf-c"]["ecoscore"]["weighting"]
            * 1e6
        )
        scores["Human toxicity, cancer, corrected"] = {
            "Indicateur": "Human toxicity, cancer, corrected",
            "Score": IMPACTS["htc-c"]["correction"][0]["weighting"]
            * scores["Human toxicity, cancer - organics"]["Score"]
            + IMPACTS["htc-c"]["correction"][1]["weighting"]
            * scores["Human toxicity, cancer - inorganics"]["Score"],
            "Unité": scores["Human toxicity, cancer"]["Unité"],
        }
        scores["Human toxicity, cancer, corrected"]["Ecoscore"] = (
            scores["Human toxicity, cancer, corrected"]["Score"]
            / IMPACTS["htc-c"]["ecoscore"]["normalization"]
            * IMPACTS["htc-c"]["ecoscore"]["weighting"]
            * 1e6
        )
        scores["Human toxicity, non-cancer, corrected"] = {
            "Indicateur": "Human toxicity, non-cancer, corrected",
            "Score": IMPACTS["htn-c"]["correction"][0]["weighting"]
            * scores["Human toxicity, non-cancer - organics"]["Score"]
            + IMPACTS["htn-c"]["correction"][1]["weighting"]
            * scores["Human toxicity, non-cancer - inorganics"]["Score"],
            "Unité": scores["Human toxicity, non-cancer"]["Unité"],
        }
        scores["Human toxicity, non-cancer, corrected"]["Ecoscore"] = (
            scores["Human toxicity, non-cancer, corrected"]["Score"]
            / IMPACTS["htn-c"]["ecoscore"]["normalization"]
            * IMPACTS["htn-c"]["ecoscore"]["weighting"]
            * 1e6
        )
        # PEF
        pef = sum(
            scores[IMPACTS[trigram]["label_en"]]["Score"]
            / IMPACTS[trigram].get("pef", {}).get("normalization", 1)
            * IMPACTS[trigram].get("pef", {}).get("weighting", 0)
            for trigram in [
                t
                for t in IMPACTS.keys()
                if t not in ("ecs", "pef", "htn-c", "etf-c", "htc-c")
            ]
        )
        # ECOSCORE
        ecs = sum(
            scores[IMPACTS[trigram]["label_en"]]["Score"]
            / IMPACTS[trigram].get("ecoscore", {}).get("normalization", 1)
            * IMPACTS[trigram].get("ecoscore", {}).get("weighting", 0)
            for trigram in [
                t
                for t in IMPACTS.keys()
                if t not in ("ecs", "pef", "htn", "etf", "htc")
            ]
        )
        for trigram in [t for t in IMPACTS.keys() if t not in ("ecs", "pef")]:
            scores[IMPACTS[trigram]["label_en"]]["%/ECS"] = (
                (scores[IMPACTS[trigram]["label_en"]]["Ecoscore"] / (ecs * 1e6) * 100)
                if ecs
                else math.inf
            )
        # cleanup to keep 16 subimpacts
        for subscore in [
            "Ecotoxicity, freshwater - part 1",
            "Ecotoxicity, freshwater - part 2",
            "Ecotoxicity, freshwater - inorganics",
            "Ecotoxicity, freshwater - organics",
            "Ecotoxicity, freshwater - organics - p.1",
            "Ecotoxicity, freshwater - organics - p.2",
            "Climate change - Biogenic",
            "Climate change - Fossil",
            "Climate change - Land use and LU change",
            "Human toxicity, cancer - inorganics",
            "Human toxicity, cancer - organics",
            "Human toxicity, non-cancer - inorganics",
            "Human toxicity, non-cancer - organics",
        ]:
            if subscore in scores:
                del scores[subscore]
    else:
        pef = ecs = None

    dfimpacts = pandas.io.formats.style.Styler(pandas.DataFrame(list(scores.values())))
    dfimpacts.set_properties(**{"background-color": "#EEE"})
    dfimpacts.format(
        formatter={
            "Score": "{:.4g}".format,
            "Ecoscore": "{:.4g}".format,
            "%/ECS": "{:.1f}",
        }
    )

    # PRODUCTION
    production = "".join(
        [
            f'<div style="font-size: 1.5em;">Production: <b>{exchange.get("amount", "N/A")} {exchange.get("unit", "N/A")}</b> of <b>{exchange.get("name", "N/A")}</b></div>'
            for exchange in activity.production()
        ]
    )

    # ACTIVITY DATA
    activity_fields = f"{production}" + dict2html(activity)

    w_details.clear_output()
    display(Markdown("## (Retrieving technosphere...)"))

    # TECHNOSPHERE
    technosphere_widgets = []
    technosphere = activity.technosphere()
    for exchange in technosphere:
        amount = exchange.get("amount", "N/A")
        unit = exchange.get("unit", "N/A")
        name = exchange.get("name", "N/A")
        upstream = get_node(key=exchange.get("input"))
        location = upstream.get("location", "N/A")
        comment = upstream.get("comment", "N/A")
        # link button
        w_link = ipywidgets.Button(description="→ visit")
        setattr(w_link, "database", f"{upstream['database']}")
        setattr(w_link, "search", f"{upstream['code']}")
        w_link.on_click(linkto)
        technosphere_widgets.append(
            ipywidgets.VBox(
                [
                    ipywidgets.HTML(
                        value=(
                            f'<details style="cursor: pointer; background-color: #EEE;">'
                            f'  <summary style="font-size: 1.5em">'
                            f"    <b>{amount} {unit}</b> of <b>{name} {{{location}}}</b>"
                            f"  </summary>"
                            f"</summary>"
                            f"{dict2html(exchange)}"
                            f"</details>"
                            f"<ul>"
                            f"  <h4>This exchange was linked to this activity of <b>{upstream['database']}</b>:</h4>"
                            f"  <li><b>Name</b>: {upstream.get('name')}</li>"
                            f"  <li><b>Location</b>: {upstream.get('location', 'N/A')}</li>"
                            f"  <li><b>Code</b>: {upstream['code']}</li>"
                            f"</ul>"
                        )
                    ),
                    w_link,
                ],
            )
        )

    w_details.clear_output()
    display(Markdown("## (Retrieving biosphere...)"))

    # BIOSPHERE
    biosphere = []
    for exchange in activity.biosphere():
        amount = exchange.get("amount", "N/A")
        unit = exchange.get("unit", "N/A")
        name = exchange.get("name", "N/A")
        input_ = get_node(key=exchange.get("input", "N/A")).as_dict()
        comment = exchange.get("comment", "N/A")
        allcfs = {
            method: bw2data.Method(method).load()
            for method in [m for m in bw2data.methods if m[0] == method]
        }
        cfs = pandas.io.formats.style.Styler(
            pandas.DataFrame(
                [
                    (
                        ", ".join(meth[1:]),
                        lookup_cf(allcfs[meth], input_["id"]),
                        bw2data.methods.get(meth, {}).get("unit", "N/A"),
                    )
                    for meth in [
                        m
                        for m in bw2data.methods
                        if m[0] == method
                        and (
                            not w_impact_category.value
                            or w_impact_category.value == m[1:]
                        )
                    ]
                ],
                columns=["Indicator", "Score", "Unit"],
            )
        )
        cfs.set_properties(**{"background-color": "#EEE"})

        biosphere.append(
            f'<details style="cursor: pointer; background-color: #EEE;"><summary style="font-size: 1.5em"><b>{amount} {unit}</b> of <b>{name}</b></summary>{dict2html(exchange)}</details>'
            "<ul>"
            f"<h4>This exchange was linked to this element of <b>{input_.get('database', 'N/A')}</b>:</h4>"
            f"<li><b>Name</b>: {input_.get('name', 'N/A')}</li>"
            f"<li><b>Code</b>: {input_.get('code', 'N/A')}</li>"
            f"<li><b>Type</b>: {input_.get('type', 'N/A')}</li>"
            f"<li><b>Categories</b>: {', '.join(input_.get('categories', []))}</li>"
            f'<li><b>CAS number</b>: <a href="https://pubchem.ncbi.nlm.nih.gov/#query={str(input_.get("CAS number")).lstrip("0")}">{str(input_.get("CAS number"))}</a></li>'
            f"<li><b>Unit</b>: {input_.get('unit', 'N/A')}</li>"
            f"<li><b>Id</b>: {input_.get('id', 'N/A')}</li>"
            f"<li><b>Comment</b>: {comment}</li>"
            f'<li><details style="cursor: pointer; background-color: #EEE;"><summary style="font-size: 1.5em"><b>Characterization factors</b></summary>{cfs.to_html(index=False)}</details></li>'
            "</ul>"
        )

    # SUBSTITUTIONS
    substitution = [
        f'<span style="font-size: 1.5em;"><b>{exchange.get("amount", "N/A")} {exchange.get("unit", "N/A")}</b> of <b>{exchange.get("name", "N/A")}</b></span>{get_activity(exchange.get("input")).get("comment", "")}'
        for exchange in activity.substitution()
    ]

    # ANALYSIS
    if w_impact_category.value:
        #        try:
        # TOP EMISSIONS
        try:
            lca.switch_method((method,) + impact_category)
        except Exception:
            analysis = "Nothing to display. Maybe you selected the biosphere?"
        else:
            lca.lcia()
            top_emissions_columns = ["Amount", "Unit", "Score", "Elementary flow"]
            top_emissions_tuples = [
                (amount, activity["unit"], score, activity)
                for (
                    score,
                    amount,
                    activity,
                ) in bw2analyzer.ContributionAnalysis().annotated_top_emissions(lca)
            ]
            top_emissions = pandas.io.formats.style.Styler(
                pandas.DataFrame(top_emissions_tuples, columns=top_emissions_columns)
            )
            top_emissions.format(
                formatter={"Amount": "{:.4g}".format, "Score": "{:.4g}".format}
            )
            top_emissions.set_properties(**{"background-color": "#EEE"})
            # TOP PROCESSES
            top_processes_columns = ["Amount", "Unit", "Score", "Activity"]
            top_processes_tuples = [
                (amount, activity["unit"], score, activity)
                for (
                    score,
                    amount,
                    activity,
                ) in bw2analyzer.ContributionAnalysis().annotated_top_processes(lca)
            ]
            top_processes = pandas.io.formats.style.Styler(
                pandas.DataFrame(top_processes_tuples, columns=top_processes_columns)
            )
            top_processes.set_properties(**{"background-color": "#EEE"})
            top_processes.format(
                formatter={"Amount": "{:.4g}".format, "Score": "{:.4g}".format}
            )
            analysis = (
                f"<h2>{', '.join(lca.method[1:])}</h2>"
                f"<h3>Top Emissions</h3>{w_csv_button(top_emissions_tuples, top_emissions_columns)}{top_emissions.to_html()}"
                f"<h3>Top Processes</h3>{w_csv_button(top_processes_tuples, top_processes_columns)}{top_processes.to_html()}"
            )
    else:
        analysis = "💡 Please select an impact category"

    w_details.clear_output()
    display(
        Markdown(
            f"# 1 {activity.get('unit', '')} of {activity.get('name', '')} "
            f"{('(in ' + ', '.join(activity.get('categories', [])) + ')') if activity.get('categories') else ''}"
        )
    )
    display(
        ipywidgets.Tab(
            titles=[
                "Data",
                "Illustration",
                f"Technosphere ({int(len(technosphere))})",
                f"Biosphere ({len(biosphere)})",
                f"Substitution ({len(substitution)})",
                "Impacts",
                "Analysis",
            ],
            children=[
                ipywidgets.HTML(value=activity_fields),
                ipywidgets.HTML(
                    value=(
                        "In this illustration, the studied activity in the center has four exchanges (in grey). "
                        "Two technosphere exchanges are linked to upstream activities (in purple), "
                        "and two biosphere activities are linked to emission or consumption of substances in the environment (in green). "
                        'The notion of "linking" in Brightway consists in setting the "input" field '
                        "of the exchanges by finding the right Activity."
                    )
                    + Illustration
                ),
                ipywidgets.VBox(technosphere_widgets),
                ipywidgets.HTML("".join(biosphere)),
                ipywidgets.HTML("".join(substitution)),
                ipywidgets.VBox(
                    [
                        ipywidgets.HTML(
                            f"<h2>µPt PEF: {1e6 * pef:10.2f}</h2>" if pef else ""
                        ),
                        ipywidgets.HTML(
                            f"<h2>Ecoscore: {1e6 * ecs:10.2f}</h2>" if ecs else ""
                        ),
                        ipywidgets.HTML(impacts_error),
                        ipywidgets.HTML(dfimpacts.to_html()),
                    ]
                ),
                ipywidgets.HTML(analysis),
            ],
        )
    )


w_project.observe(changed_project, names="value")
w_database.observe(changed_database, names="value")
w_search.observe(changed_search, names="value")
w_limit.observe(changed_limit, names="value")
w_activity.observe(changed_activity, names="value")
w_method.observe(changed_method, names="value")
w_impact_category.observe(changed_impact_category, names="value")

details = ipywidgets.VBox(
    [
        w_panel,
        w_back_button,
    ],
)
details.add_class("details")
display(
    ipywidgets.HBox(
        [
            ipywidgets.VBox(
                [
                    w_project,
                    w_database,
                    w_method,
                    w_impact_category,
                    w_search,
                    w_limit,
                    w_activity,
                ],
                layout=ipywidgets.Layout(margin="2em"),
            ),
            details,
        ],
        layout=ipywidgets.Layout(
            display="flex",
            flex_flow="row",
            padding="2em",
            justify_content="flex-start",
        ),
    )
)
display(w_results)
display(w_details)
