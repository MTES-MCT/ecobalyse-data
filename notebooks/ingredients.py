"""
This file is the ingredient/activity editor Jupyter Notebook
"""

if True:  # just to bypass the ruff warning
    print("Please wait")
import os
import sys
import uuid

# don"t display bw2data startup output
if True:
    sys.stdout = open(os.devnull, "w")
from bw2data.project import projects

if True:
    sys.stdout = sys.__stdout__
import base64
import csv
import io
import json
import shutil
import subprocess
import urllib.parse

import bw2calc
import bw2data
import ipywidgets
import pandas
import pandas.io.formats.style
import requests
from flatdict import FlatDict
from IPython.display import display

from common import spproject

PROJECT = "ecobalyse"
ACTIVITIES = "food/activities.json"
ACTIVITIES_TEMP = "activities.%s.json"
AGRIBALYSE = "Agribalyse 3.1.1"
CROP_GROUPS = [("", None)] + [
    (x, x)
    for x in (
        "BLE TENDRE",
        "MAIS GRAIN ET ENSILAGE",
        "ORGE",
        "AUTRES CEREALES",
        "COLZA",
        "TOURNESOL",
        "AUTRES OLEAGINEUX",
        "PROTEAGINEUX",
        "PLANTES A FIBRES",
        "SEMENCES",
        "GEL (surfaces gelées sans production)",
        "GEL INDUSTRIEL",
        "AUTRES GELS",
        "RIZ",
        "LEGUMINEUSES A GRAIN",
        "FOURRAGE",
        "ESTIVES LANDES",
        "PRAIRIES PERMANENTES",
        "PRAIRIES TEMPORAIRES",
        "VERGERS",
        "VIGNES",
        "FRUITS A COQUES",
        "OLIVIERS",
        "AUTRES CULTURES INDUSTRIELLES",
        "LEGUMES-FLEURS",
        "CANNE A SUCRE",
        "ARBORICULTURE",
        "DIVERS",
        "BOVINS VIANDE",
        "BOVINS LAIT",
        "OVINS VIANDE",
        "OVINS LAIT",
        "VOLAILLES",
        "PORCINS",
    )
]
ANIMAL_GROUP1 = [
    ("", None),
    ("Bétail", "cattle"),
    ("Porc", "pig"),
    ("Volaille", "poultry"),
    ("Mouton", "sheep"),
]
ANIMAL_GROUP2 = [
    ("", None),
    ("Vache", "cow"),
    ("Porc", "pig"),
    ("Poulet", "chicken"),
    ("Mouton", "sheep"),
]
ANIMAL_PRODUCT = [("", None), ("Oeuf", "egg"), ("Lait", "milk"), ("Viande", "meat")]

projects.set_current(PROJECT)
# projects.create_project(PROJECT, activate=True, exist_ok=True)

main_output = ipywidgets.Output()
list_output = ipywidgets.Output()
git_output = ipywidgets.Output()
reset_output = ipywidgets.Output()
file_output = ipywidgets.Output()
save_output = ipywidgets.Output()
surface_output = ipywidgets.Output()

pandas.set_option("display.max_columns", 500)
pandas.set_option("display.max_rows", 500)
pandas.set_option("notebook_repr_html", True)
pandas.set_option("max_colwidth", 15)


def dbsearch(db, term, **kw):
    return bw2data.Database(db).search(term, **kw)


def cleanup_json(activities):
    """consistency of the json file"""
    for i, a in enumerate(activities):
        # remove categories for non-ingredients
        if "ingredient" not in a["process_categories"]:
            for x in (
                "ingredient_categories",
                "rawToCookedRatio",
                "density",
                "inediblePart",
                "transportCooling",
                "visible",
                "explain",
                "animalGroup1",
                "animalGroup2",
                "animalProduct",
                "cropGroup",
                "landOccupation",
                "scenario",
            ):
                if x in a:
                    del activities[i][x]
        else:
            # remove empty SE
            for x in ("animalGroup1", "animalGroup2", "animalProduct", "cropGroup"):
                if x in a and a[x] is None:
                    del a[x]

    return activities


def save_activities(activities):
    with open(ACTIVITIES_TEMP % w_contributor.value, "w") as fp:
        fp.write(
            json.dumps(
                cleanup_json([from_flat(from_pretty(i)) for i in activities.values()]),
                indent=2,
                ensure_ascii=False,
            )
        )
    display_main()


def to_flat(d):
    return dict(FlatDict(d, delimiter="."))


def from_flat(d):
    return FlatDict(d, delimiter=".").as_dict()


def reverse(d):
    """turn the values of a dict into keys and keys into values"""
    return {v: k for k, v in d.items()}


FIELDS = {
    # process attributes
    "id": "id",
    "alias": "alias",
    "name": "Nom",
    "database": "Base de données",
    "search": "Termes de recherche",
    "defaultOrigin": "Origine par défaut",
    "process_categories": "Catégories de procédé",
    # ingredients attributes
    "ingredient_categories": "Catégories d'ingrédient",
    "rawToCookedRatio": "Cooked/Raw ratio",
    "density": "Densité",
    "inediblePart": "Part non comestible",
    "transportCooling": "Transport réfrigéré",
    "visible": "Visible",
    "explain": "Commentaires",
    # EcosystemicServices for animal products
    "animalGroup1": "Groupe d'élevage 1",
    "animalGroup2": "Groupe d'élevage 2",
    "animalProduct": "Produit animal",
    # EcosystemicServices for other products
    "cropGroup": "Groupe de culture",
    "landOccupation": "Empreinte terrestre (m²a)",
    "scenario": "Scenario",
}


def to_pretty(d):
    """turn a dict with dotted keys to a dict with pretty keys"""
    return {FIELDS[k]: v for k, v in d.items() if FIELDS.get(k)}


def from_pretty(d):
    """turn a dict with pretty keys to a dict with dotted keys"""
    activity = {reverse(FIELDS)[k]: v for k, v in d.items()}
    return activity


def read_activities():
    """Return the activities as a dict indexed with id"""

    def read_temp():
        with open(ACTIVITIES_TEMP % w_contributor.value) as fp:
            fs = {i["id"]: i for i in [to_pretty(to_flat(i)) for i in json.load(fp)]}
            for k, v in fs.items():
                v.setdefault("Base de données", AGRIBALYSE)
                fs[k] = v
            return fs

    if not os.path.exists(ACTIVITIES_TEMP % w_contributor.value):
        shutil.copy(ACTIVITIES, ACTIVITIES_TEMP % w_contributor.value)
    try:
        activities = read_temp()
    except json.JSONDecodeError:
        shutil.copy(ACTIVITIES, ACTIVITIES_TEMP % w_contributor.value)
        activities = read_temp()

    return activities


# WIDGETS
## technical identifier of the activity (for API/URL/FK)
style = {"description_width": "initial"}
w_contributor = ipywidgets.Dropdown(
    options=[
        "Écobalyse",
        "ITERG",
        "ACTALIA",
        "IFV",
        "ADEME",
        "ITAB",
        "CTCPA",
        "ITAVI",
        "IDELE",
        "Terres Inovia",
        "CTIFL",
    ],
    value=None,
    style=style,
    description="Contributeur : ",
)
w_filter = ipywidgets.Text(placeholder="Search", style=style)

w_id = ipywidgets.Text(placeholder="id", style=style, disabled=True)

w_alias = ipywidgets.Combobox(
    placeholder="wheat-organic",
    style=style,
    options=tuple(
        [""] + [activity["alias"] for activity in list(read_activities().values())]
    ),
)
## Name of the activity (for users)
w_name = ipywidgets.Text(
    placeholder="Farine bio",
    style=style,
)
## Is the activity an ingredient?
w_ingredient = ipywidgets.Checkbox(indent=False, style=style, value=False)
## brightway search terms to find the activity
w_database = ipywidgets.Dropdown(
    options=[d for d in list(bw2data.databases) if str(d) != "biosphere3"],
    value=AGRIBALYSE if AGRIBALYSE in bw2data.databases else "",
)
w_search = ipywidgets.Text(placeholder="wheat FR farm", style=style)
w_results = ipywidgets.RadioButtons(
    rows=1,
    options=[""],
    style=style,
    layout=ipywidgets.Layout(width="auto", overflow="scroll"),
    disabled=True,
)
## default origin
w_defaultOrigin = ipywidgets.Dropdown(
    options=[
        ("France (à plus de 95%)", "France"),
        ("Europe ou Maghreb (à plus de 95%)", "EuropeAndMaghreb"),
        ("Hors Europe ou Maghreb (à plus de 5%)", "OutOfEuropeAndMaghreb"),
        (
            "Par avion, hors Europe ou Maghreb (mangue, haricots, ...)",
            "OutOfEuropeAndMaghrebByPlane",
        ),
    ],
    style=style,
)
w_process_categories = ipywidgets.TagsInput(
    allowed_tags=[
        "ingredient",
        "material",
        "energy",
        "packaging",
        "processing",
        "transformation",
        "transport",
        "waste treatment",
    ],
    style=style,
    allow_duplicates=False,
)
w_ingredient_categories = ipywidgets.TagsInput(
    allowed_tags=[
        "animal_product",
        "dairy_product",
        "grain_raw",
        "grain_processed",
        "nut_oilseed_raw",
        "nut_oilseed_processed",
        "misc",
        "spice_condiment_additive",
        "vegetable_fresh",
        "vegetable_processed",
        "organic",
        "bleublanccoeur",
    ],
    style=style,
    allow_duplicates=False,
)
## Transport cooling
w_cooling = ipywidgets.Dropdown(
    options=[
        ("Non", "none"),
        ("Toujours", "always"),
        ("Une fois transformé", "once_transformed"),
    ],
    style=style,
)
# Cooked/Raw ratio
w_rawToCookedRatio = ipywidgets.Dropdown(
    options=[
        (
            "1.0 (Prod laitiers, noix, boiss liquides, herbes, fruits et légumes séchés, farines, sel, sucre, épices, cornichons, câpres, condiments)",
            1.0,
        ),
        ("2,330 (Légumineuses)", 2.33),
        ("2,259 (Céréales)", 2.259),
        ("0,974 (Oeufs)", 0.974),
        ("0,856 (Fruits et légumes)", 0.856),
        ("0,819 (Poissons et fruits de mer)", 0.819),
        ("0,792 (Viandes rouges)", 0.792),
        ("0,755 (Volaille)", 0.755),
        ("0,730 (Abats)", 0.730),
    ]
)
w_density = ipywidgets.Dropdown(
    options=[
        ("", 0),
        ("0,6375 (Pomme de terre, frites, racines)", 0.6375),
        ("0,6195 (Onion, poireau, échalote, chou-rave)", 0.6195),
        ("0,3980 (Aubergine, courgette)", 0.398),
        ("0,3620 (Chou, asperge, artichaut, chou de Bruxelles, citrouille)", 0.362),
        ("0,5750 (Citron, agrumes)", 0.575),
        ("0,2710 (Haricots verts/blancs/plat, soja)", 0.271),
        ("0,2355 (Chou-fleur, brocoli, romanesco)", 0.2355),
        (
            "0,2400 (Niébé, flageolet, mungo, petits pois, légumineuses, lentilles, noix, graines, maïs)",
            0.24,
        ),
        (
            "0,1180 (Épinard, laitue, endives, cresson, champignons, autres légers)",
            0.118,
        ),
        ("0,2950 (Poivrons)", 0.295),
        (
            "0,4470 (Concombre, melon, pastèque, tous fruits et baies, noix de coco, céléri, rhubarbe (autres riches en eau)",
            0.447,
        ),
        (
            "1.0000 (Autres, oeuf, algues, fruits de mer, laitiers, viande, farines, poisson, sauce tomate)",
            1.0,
        ),
    ],
)
## inedible part of the ingredient
w_inedible = ipywidgets.Dropdown(
    options=[
        ("", 1),
        ("◼ FRUITS ◼", ""),
        (" 3% (tomate, mures, myrtilles, framboises, fraises)", 0.03),
        ("10% (pommes, poire, raisin)", 0.1),
        (
            "20% (abricot, groseille, mandarine, mangue, orange, pêche, prune, grenade)",
            0.2,
        ),
        ("30% (banane, pamplemousse, citron)", 0.3),
        ("40% (melon)", 0.4),
        ("50% (amandes, ananas, noix)", 0.5),
        ("◼ LEGUMES ◼", ""),
        (" 0% (pois verts)", 0),
        (" 3% (céleri, céleri vert, poivron, radis, épinard)", 0.03),
        (
            "10% (basilic, betterave, chou de Bruxelles, carotte, manioc, céleri-rave, artichaut chinois/japonais, coriandre, concombre, aubergine)",
            0.1,
        ),
        (
            "10% (harico vert, topinambour, menthe, champignon, onion, persil, pomme de terre, échalote, patate douce, igname)",
            0.1,
        ),
        (
            "20% (estragon, navet, broccoli, chou, chou-fleur, chicorée, endive, fenouil, cresson, petits pois, poireau, citrouille, endive rouge, salsifis)",
            0.2,
        ),
        ("30% (avocat)", 0.3),
        ("40% (asperge, scarole, laitue, salade)", 0.4),
        ("50% (chataîgne, olive)", 0.5),
        ("60% (artichaut)", 0.6),
        ("◼ AUTRES ◼", ""),
        (" 0% (viande désossée)", 0),
        ("20% (oeuf, viande avec os)", 0.2),
    ]
)
## Enable/disable the ingredient
w_visible = ipywidgets.Checkbox(indent=False, style=style, value=True)
w_explain = ipywidgets.Textarea(
    placeholder="Indiquez tous les commentaires nécessaires à la bonne compréhension des choix qui ont été faits, afin d'assurer la traçabilité de l'info",
    layout=ipywidgets.Layout(width="450px", height="200px"),
)

## COMPLEMENTS

# parameters used to compute ecosystemicServices
w_animalGroup1 = ipywidgets.Dropdown(options=ANIMAL_GROUP1, value=None)
w_animalGroup2 = ipywidgets.Dropdown(options=ANIMAL_GROUP2, value=None)
w_animalProduct = ipywidgets.Dropdown(options=ANIMAL_PRODUCT, value=None)
w_cropGroup = ipywidgets.Dropdown(options=CROP_GROUPS, style=style, value=None)
w_land_footprint = ipywidgets.FloatText()
w_scenario = ipywidgets.Dropdown(options=["reference", "organic", "import"], value=None)

# buttons
save_button_tooltip = "Enregistre l'ingrédient créé ou modifié"
save_button_tooltip_non_unique = (
    "Vos termes de recherche doivent donner un seul résultat"
)
savebutton = ipywidgets.Button(
    description="Enregistrer localement",
    button_style="warning",  # 'success', 'info', 'warning', 'danger' or ''
    tooltip=save_button_tooltip,
    icon="check",
    layout=ipywidgets.Layout(width="auto"),
)
delbutton = ipywidgets.Button(
    description="Supprimer localement",
    button_style="danger",  # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Supprime l'ingrédient correspondant à l'identifiant 'id'",
    icon="trash",
    layout=ipywidgets.Layout(width="auto"),
)
resetbutton = ipywidgets.Button(
    description="Réinitialiser",
    button_style="success",  # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Annuler tous les changements et revenir à l'état déjà publié",
    icon="sparkles",
)
clear_reset_button = ipywidgets.Button(
    description="X",
    button_style="",  # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Nettoyer sous le bouton",
    layout=ipywidgets.Layout(width="50px"),
)
clear_git_button = ipywidgets.Button(
    description="X",
    button_style="",  # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Nettoyer sous le bouton",
    layout=ipywidgets.Layout(width="50px"),
)
clear_save_button = ipywidgets.Button(
    description="X",
    button_style="",  # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Nettoyer sous les boutons",
    layout=ipywidgets.Layout(width="50px"),
)
commitbutton = ipywidgets.Button(
    description="Publier pour validation",
    button_style="danger",  # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Publier et soumettre à validation",
    icon="code-commit",
    layout=ipywidgets.Layout(width="auto"),
)
uploadbutton = ipywidgets.FileUpload(
    description="Upload CSV",
    accept=".csv",
    multiple=False,
)
surfacebutton = ipywidgets.Button(
    description="Calculer la surface",
    button_style="danger",  # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Calcule la surface dans Brightway et Simapro et alimente le champ ci-dessous",
    icon="sparkles",
    layout=ipywidgets.Layout(width="150px"),
)


def downloadbutton(contents, columns):
    csvfile = io.StringIO()
    writer = csv.DictWriter(csvfile, fieldnames=columns)
    writer.writeheader()
    for item in contents:
        writer.writerow(item)
    csvfile.seek(0)
    contents = csvfile.read()
    return """
        <a download="{filename}" href="data:text/csv;base64,{payload}" download>
        <button class="p-Widget jupyter-widgets jupyter-button widget-button mod-warning">Download CSV</button>
        </a>
    """.format(
        payload=base64.b64encode(contents.encode()).decode(), filename="export.csv"
    )


@list_output.capture()
def list_activities(filter=""):
    activities = {
        i: a
        for i, a in read_activities().items()
        if not filter
        or filter.lower() in a["Nom"].lower()
        or filter.lower() in a["alias"].lower()
    }
    columns = list(FIELDS.values())
    df = pandas.io.formats.style.Styler(
        pandas.DataFrame(activities.values(), columns=columns)
    )
    df.set_properties(**{"background-color": "#EEE"})
    list_output.clear_output()
    display(
        ipywidgets.HTML(
            f"<h2>List of {len(activities)} processes/ingredients:</h2>"
            f"{downloadbutton(activities.values(), columns)}"
            f"{df.to_html()}",
            layout=ipywidgets.Layout(width="auto", overflow="scroll"),
        ),
    )


class printer(str):
    def __repr__(self):
        return self


@file_output.capture()
def display_output_file():
    with open(ACTIVITIES_TEMP % w_contributor.value) as fp:
        display(
            printer(json.dumps(json.load(fp), indent=2, ensure_ascii=False)),
            display_id=True,
        )


def clear_all():
    clear_form()
    list_output.clear_output()
    file_output.clear_output()
    main_output.clear_output()


def clear_form():
    w_id.value = str(uuid.uuid4())
    w_alias.options = tuple(
        [""] + [activity["alias"] for activity in list(read_activities().values())]
    )
    w_alias.value = ""
    w_name.value = ""
    w_database.value = AGRIBALYSE if AGRIBALYSE in bw2data.databases else ""
    w_search.value = ""
    w_results.options = [""]
    w_results.value = ""
    w_process_categories.value = []
    w_ingredient_categories.value = []
    w_explain.value = ""
    w_defaultOrigin.value = "EuropeAndMaghreb"
    w_rawToCookedRatio.value = 1
    w_density.value = 0
    w_inedible.value = 1
    w_cooling.value = "none"
    w_visible.value = True
    w_animalGroup1.value = None
    w_animalGroup2.value = None
    w_animalProduct.value = None
    w_cropGroup.value = None
    w_land_footprint.value = 0
    w_scenario.value = None


def set_field(field, value, default):
    """the field is supposed to be empty.
    We store the default value but set field.empty=True
    """
    if value is None:
        field.value = default
    else:
        field.value = value
    return field


def display_of(activity):
    return f"{activity['name']} ({activity.get('unit', '(aucune)')}) code:{activity['code']}"


@main_output.capture()
def changed_contributor(_):
    display_main()


w_contributor.observe(changed_contributor, names="value")


def changed_alias(change):
    if not change.new:
        clear_form()
        save_output.clear_output()
        return
    i = None
    for activity in read_activities().values():
        if activity["alias"] == change.new:
            i = from_pretty(activity)
            break

    if not i:
        w_id.value = str(uuid.uuid4())
        return

    set_field(w_id, i.get("id"), "")
    set_field(w_name, i.get("name"), "")
    terms = i.get("search", "")
    set_field(w_database, i.get("database"), "")
    set_field(w_search, i.get("search"), "")
    res = dbsearch(w_database.value, terms)
    if res:
        w_results.options = [[display_of(r) for r in res][0]]
    else:
        w_results.options = []
    set_field(w_defaultOrigin, i.get("defaultOrigin"), "EuropeAndMaghreb")
    set_field(w_explain, i.get("explain"), "")
    set_field(w_process_categories, i.get("process_categories"), [])
    set_field(w_ingredient_categories, i.get("ingredient_categories"), [])
    set_field(w_rawToCookedRatio, i.get("rawToCookedRatio"), 1)
    set_field(w_density, i.get("density"), 0)
    set_field(w_inedible, i.get("inediblePart"), 0)
    set_field(w_cooling, i.get("transportCooling"), "none")
    set_field(w_visible, i.get("visible"), True)
    set_field(w_scenario, i.get("scenario"), None)
    set_field(w_animalGroup1, i.get("animalGroup1"), None)
    set_field(w_animalGroup2, i.get("animalGroup2"), None)
    set_field(w_animalProduct, i.get("animalProduct"), None)
    set_field(w_cropGroup, i.get("cropGroup"), None)
    set_field(w_land_footprint, i.get("landOccupation"), 0)


w_alias.observe(changed_alias, names="value")


def changed_search_to(field):
    def changed_search(change):
        activity = None
        results = list(dbsearch(w_database.value, w_search.value, limit=10))
        if w_search.value in [a["name"] for a in results]:
            exacts = [a for a in results if a["name"] == w_search.value]
            results = exacts
            activity = results[0]
        else:
            if len(results) == 1:
                activity = results[0]
            else:
                savebutton.disabled = True
                savebutton.tooltip = save_button_tooltip_non_unique
        field.rows = len(results)
        field.options = [display_of(r) for r in results]
        if activity is not None:
            field.value = display_of(activity)
            setattr(surfacebutton, "activity", activity)
            savebutton.disabled = False
            savebutton.tooltip = save_button_tooltip
        elif hasattr(surfacebutton, "activity"):
            field.value = None
            delattr(surfacebutton, "activity")

    return changed_search


changed_database_to = changed_search_to


def changed_filter(change):
    list_output.clear_output()
    list_activities(change.new)


w_filter.observe(changed_filter, names="value")


@save_output.capture()
def add_activity(_):
    activity = {
        "id": w_id.value,
        "alias": w_alias.value,
        "name": w_name.value.strip(),
        "database": w_database.value,
        "search": w_search.value.strip(),
        "process_categories": w_process_categories.value,
        "ingredient_categories": w_ingredient_categories.value,
        "defaultOrigin": w_defaultOrigin.value,
        "rawToCookedRatio": w_rawToCookedRatio.value,
        "density": w_density.value,
        "inediblePart": w_inedible.value,
        "transportCooling": w_cooling.value,
        "visible": w_visible.value,
        "explain": w_explain.value.strip(),
        "scenario": w_scenario.value,
        "landOccupation": w_land_footprint.value,
    }
    activity.update(
        {
            "animalGroup1": w_animalGroup1.value,
            "animalGroup2": w_animalGroup2.value,
            "animalProduct": w_animalProduct.value,
        }
        if "animalProduct" in w_ingredient_categories.value
        or "dairy_product" in w_ingredient_categories.value
        else {
            "cropGroup": w_cropGroup.value,
        }
    )
    activity = {k: v for k, v in activity.items() if v != ""}
    activities = read_activities()

    if "id" not in activity:
        display(
            ipywidgets.HTML(
                "<pre style='color: red'>Vous devez rentrer un identifiant d'ingrédient (en anglais, en minuscule, sans espace</pre>"
            )
        )
    elif (
        activity["alias"].lower() != activity["alias"]
        or activity["alias"].replace(" ", "") != activity["alias"]
    ):
        display(
            ipywidgets.HTML(
                "<pre style='color: red'>L'alias doit être en minuscule et sans espace</pre>"
            )
        )

    elif activity["alias"] in [
        a["alias"] for a in activities.values() if a["id"] != activity["id"]
    ]:
        display(
            ipywidgets.HTML(
                f"<pre style='color: red'>Un procédé ou ingrédient avec cet alias existe déjà : {activity['id']}</pre>"
            )
        )
    elif activity["name"] in [
        a["Nom"] for a in activities.values() if a["id"] != activity["id"]
    ]:
        display(
            ipywidgets.HTML(
                f"<pre style='color: red'>Un procédé ou ingrédient avec ce nom existe déjà : {activity['id']}</pre>"
            )
        )
    else:
        save_output.clear_output()
        activities.update({activity["id"]: to_pretty(activity)})
        save_activities(activities)


def delete_activity(_):
    activities = read_activities()
    if w_id.value in activities:
        del activities[w_id.value]
        save_activities(activities)


def current_branch():
    return (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True
        )
        .stdout.decode()
        .strip()
    )


def reset_branch():
    branch = current_branch()
    if subprocess.run(["git", "reset", "--hard"], capture_output=True).returncode != 0:
        display(
            ipywidgets.HTML(
                "<pre style='color: red'>ÉCHEC de la commande: git reset --hard"
            )
        )
    elif subprocess.run(["git", "fetch", "--all"], capture_output=True).returncode != 0:
        display(
            ipywidgets.HTML(
                "<pre style='color: red'>ÉCHEC de la commande: git fetch --all"
            )
        )
    elif (
        subprocess.run(
            ["git", "checkout", f"origin/{branch}"], capture_output=True
        ).returncode
        != 0
    ):
        display(
            ipywidgets.HTML(
                f"<pre style='color: red'>ÉCHEC de la commande: git checkout origin/{branch}"
            )
        )
    elif (
        subprocess.run(
            ["git", "branch", "-D", f"{branch}"], capture_output=True
        ).returncode
        != 0
    ):
        display(
            ipywidgets.HTML(
                f"<pre style='color: red'>ÉCHEC de la commande: git branch -D {branch}"
            )
        )
    elif (
        subprocess.run(
            ["git", "branch", f"{branch}", f"origin/{branch}"], capture_output=True
        ).returncode
        != 0
    ):
        display(
            ipywidgets.HTML(
                f"<pre style='color: red'>ÉCHEC de la commande: git branch {branch} origin/{branch}"
            )
        )
    elif (
        subprocess.run(["git", "checkout", f"{branch}"], capture_output=True).returncode
        != 0
    ):
        display(
            ipywidgets.HTML(
                f"<pre style='color: red'>ÉCHEC de la commande: git checkout {branch}"
            )
        )
    else:
        display(
            ipywidgets.HTML(
                "<pre style='color: red'>ÉCHEC. Prévenez l'équipe Écobalyse"
            )
        )


def compute_surface(_):
    activity = getattr(surfacebutton, "activity")
    if not activity:
        return
    surfacebutton.disabled = True
    display_surface()
    lca = bw2calc.LCA({activity: 1})
    method = ("selected LCI results", "resource", "land occupation")
    try:
        lca.lci()
        lca.switch_method(method)
        lca.lcia()
        bwsurface = lca.score
        bwoutput = str(bwsurface)
    except Exception as e:
        bwsurface = 0
        bwoutput = repr(e)
    try:
        process = urllib.parse.quote(activity["name"], encoding=None, errors=None)
        project, library = spproject(activity)
        project = urllib.parse.quote(project, encoding=None, errors=None)
        library = urllib.parse.quote(library, encoding=None, errors=None)
        method = urllib.parse.quote("Selected LCI results", encoding=None, errors=None)
        spsurface = (
            json.loads(
                requests.get(
                    f"http://simapro.ecobalyse.fr:8000/impact?process={process}&project={project}&library={library}&method={method}"
                ).content
            )
            .get("Land occupation", {})
            .get("amount", 0)
        )
        spoutput = str(spsurface)
        spsurface = float(spsurface)
    except Exception as e:
        spsurface = 0
        spoutput = repr(e)
    w_land_footprint.value = spsurface or bwsurface
    display_surface(bwoutput, spoutput)
    surfacebutton.disabled = False


@surface_output.capture()
def display_surface(bwoutput=None, spoutput=None):
    surface_output.clear_output()
    if not bwoutput and not spoutput:
        display(ipywidgets.HTML("Computing surface... (please wait at least 15s)"))
    else:
        display(
            ipywidgets.HTML(
                f"<ul><li>Brightway: {bwoutput}<li>SimaPro: {spoutput}</ul>"
            )
        )


@reset_output.capture()
def reset_activities(_):
    branch = current_branch()
    if (
        subprocess.run(
            ["git", "pull", "origin", f"{branch}"], capture_output=True
        ).returncode
        != 0
    ):
        display(
            ipywidgets.HTML(
                f"<pre style='color: red'>ÉCHEC de la commande: git pull origin {branch}. Prénenez l'équipe Écobalyse'"
            )
        )
        reset_branch()
    else:
        display(
            ipywidgets.HTML(
                f"<pre style='color: green'>SUCCÈS. La liste d'ingrédients et procédés est à jour avec la branche {branch}"
            )
        )

    shutil.copy(ACTIVITIES, ACTIVITIES_TEMP % w_contributor.value)
    w_alias.options = tuple(
        [""] + [activity["alias"] for activity in list(read_activities().values())]
    )
    display_main()


def clear_git_output(_):
    git_output.clear_output()


def clear_save_output(_):
    save_output.clear_output()


def clear_reset_output(_):
    reset_output.clear_output()


@list_output.capture()
def upload_activities(_):
    csvfile = io.StringIO()
    csvfile.write(uploadbutton.value[0].content.tobytes().decode("utf-8"))
    csvfile.seek(0)
    save_activities({row["id"]: row for row in csv.DictReader(csvfile)})


@git_output.capture()
def commit_activities(_):
    git_output.clear_output()
    previous_branch = current_branch()
    branch = "ingredients"
    display(ipywidgets.HTML("Veuillez patienter quelques secondes…"))
    prettier = ["npx", "prettier", "--write", ACTIVITIES]
    git_add = ["git", "add", ACTIVITIES]
    git_commit = [
        "git",
        "commit",
        "--no-verify",
        "-m",
        f"Changed ingredients (contributed by {w_contributor.value})",
    ]
    git_pull = ["git", "pull", "origin", f"{branch}"]
    git_push = ["git", "push", "origin", f"{branch}"]
    commands = [prettier, git_add, git_commit, git_pull, git_push]

    subprocess.run(["git", "checkout", branch])

    shutil.copy(ACTIVITIES_TEMP % w_contributor.value, ACTIVITIES)

    success = True
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            display(
                ipywidgets.HTML(
                    f"<pre style='color: red'>ÉCHEC de la commande : `{' '.join(command)}`. {result.stderr} - {result.stdout}"
                )
            )
            success = False
            break

    if success:
        display(
            ipywidgets.HTML(
                "<pre style='color: green'>SUCCÈS. Merci !! Vous pouvez prévenir l'équipe Écobalyse qu'il y a des nouveautés en attente de validation"
            )
        )

        # Go back to the old branch
        subprocess.run(["git", "checkout", previous_branch])
    else:
        display(
            ipywidgets.HTML(
                "<pre style='color: red'>ÉCHEC. Prévenez l'équipe Écobalyse"
            )
        )


@main_output.capture()
def display_main():
    clear_all()
    display(
        ipywidgets.HTML("Sélectionnez le contributeur")
    ) if not w_contributor.value else display(
        ipywidgets.Tab(
            titles=[
                "Liste",
                "Formulaire",
                "Aperçu du fichier",
                "Publier",
                "Documentation",
            ],
            layout=ipywidgets.Layout(width="auto", overflow="scroll"),
            children=[
                ipywidgets.VBox(
                    (
                        ipywidgets.HBox(
                            (
                                resetbutton,
                                uploadbutton,
                                clear_reset_button,
                            )
                        ),
                        w_filter,
                        reset_output,
                        list_output,
                    )
                ),
                ipywidgets.VBox(
                    (
                        ipywidgets.HTML(
                            "Identifiant unique Ecobalyse, auto-généré, non modifiable"
                        ),
                        ipywidgets.HBox(
                            (
                                ipywidgets.Label(
                                    FIELDS["id"],
                                ),
                                w_id,
                            ),
                        ),
                        ipywidgets.HTML(
                            "Alias technique de l'ingrédient à ajouter, modifier ou supprimer (en anglais, sans espace) : "
                        ),
                        ipywidgets.HBox(
                            (
                                ipywidgets.Label(
                                    FIELDS["alias"],
                                ),
                                w_alias,
                            ),
                        ),
                        ipywidgets.HBox((savebutton, delbutton, clear_save_button)),
                        ipywidgets.VBox((save_output,)),
                        ipywidgets.HTML(
                            "<hr/>Nom de l'ingrédient tel qu'il va apparaître dans l'outil (en français) :"
                        ),
                        ipywidgets.HBox(
                            (
                                ipywidgets.Label(
                                    FIELDS["name"],
                                ),
                                w_name,
                            ),
                        ),
                        ipywidgets.HTML(
                            """<hr/>Mots clés permettant d'avoir un résultat unique dans la liste des résultats.
                          Il faut rester le plus succint possible pour que les termes de recherche restent
                          valables dans une future version d'Agribalyse. Si vous ne pouvez pas différencier deux procédés vous
                          pouvez saisir son nom exact ou préciser son code avec: <i>code:1234567890...</i>. Vous pouvez vous
                          aider de l'explorateur dans un autre onglet pour naviguer dans Agribalyse."""
                        ),
                        ipywidgets.HBox(
                            (
                                ipywidgets.Label("Base de données"),
                                w_database,
                            ),
                        ),
                        ipywidgets.HBox(
                            (
                                ipywidgets.Label("Termes de recherche"),
                                w_search,
                            ),
                        ),
                        ipywidgets.HBox(
                            (
                                ipywidgets.Label(
                                    "Résultats",
                                ),
                                w_results,
                            ),
                        ),
                        ipywidgets.HBox(
                            (
                                ipywidgets.Label(
                                    FIELDS["process_categories"],
                                ),
                                w_process_categories,
                            ),
                        ),
                        ipywidgets.Accordion(
                            titles=["Si le procédé est un ingrédient"],
                            children=[
                                ipywidgets.VBox(
                                    (
                                        ipywidgets.HTML(
                                            """Indiquez « visible » pour que l'ingrédient soit visible
                                          dans Écobalyse. (Un ingrédient en attente peut être publié
                                          mais invisible) :"""
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["visible"],
                                                ),
                                                w_visible,
                                            ),
                                        ),
                                        ipywidgets.HTML(
                                            """<hr/>Sélectionnez la catégorie principale de
                                          l'ingrédient. (par exemple un sucre de canne peut être
                                          catégorisé comme légume transformé, par analogie avec le
                                          sucre de betterave). Si l'ingrédient dispose d'un label
                                          (bio, bleublanccoeur) ajoutez cette catégorie à la suite de
                                          la catégorie principale """
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["ingredient_categories"],
                                                ),
                                                w_ingredient_categories,
                                            ),
                                        ),
                                        ipywidgets.HTML(
                                            """<hr/>Indiquez l'origine par défaut. Se référer à la <a
                                          style="color:blue"
                                          href="https://fabrique-numerique.gitbook.io/ecobalyse/alimentaire/transport">documentation
                                          Écobalyse</a>"""
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["defaultOrigin"],
                                                ),
                                                w_defaultOrigin,
                                            ),
                                        ),
                                        ipywidgets.HTML(
                                            """<hr/>Le rapport cuit/cru est nécessaire pour le calcul
                                          d'impact. Si besoin se référer à la <a style="color:blue"
                                          href="https://fabrique-numerique.gitbook.io/ecobalyse/alimentaire/rapport-cru-cuit">documentation
                                          Écobalyse</a>, page « rapport cuit/cru » qui reprend les
                                          règles Agribalyse :"""
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["rawToCookedRatio"],
                                                ),
                                                w_rawToCookedRatio,
                                            ),
                                        ),
                                        ipywidgets.HTML(
                                            """ <hr/>La densité est nécessaire pour le calcul d'impact.
                                          Si besoin se référer à la <a style="color:blue"
                                          href="https://fabrique-numerique.gitbook.io/ecobalyse/alimentaire/densite">documentation
                                          Écobalyse</a>, page « densité » , qui reprend les règles
                                          Agribalyse"""
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["density"],
                                                ),
                                                w_density,
                                            ),
                                        ),
                                        ipywidgets.HTML(
                                            """<hr/>La part non comestible est nécessaire pour le calcul
                                          d'impact. Si besoin se référer à la <a style="color:blue"
                                          href="https://fabrique-numerique.gitbook.io/ecobalyse/alimentaire/part-non-comestible">documentation
                                          Écobalyse</a>, page « part non-comestible, qui reprend les
                                          règles Agribalyse. En l'absence d'info, prendre un
                                          ingrédient équivalent en terme de part non comestible"""
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["inediblePart"],
                                                ),
                                                w_inedible,
                                            ),
                                        ),
                                        ipywidgets.HTML(
                                            "<hr/>Sélectionnez le mode de transport : régrigéré ou non"
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["transportCooling"],
                                                ),
                                                w_cooling,
                                            ),
                                        ),
                                        ipywidgets.HTML(
                                            """<hr/>Indiquez tous les commentaires nécessaires à la bonne
                                          compréhension des choix qui ont été faits, afin d'assurer la
                                          traçabilité de l'info"""
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["explain"],
                                                ),
                                                w_explain,
                                            ),
                                        ),
                                        ipywidgets.HTML(
                                            """<hr/>Pour les services écosystémiques, voir
                                              la <a style="color:blue"
                                              href="https://fabrique-numerique.gitbook.io/ecobalyse/alimentaire/complements-hors-acv">documentation</a>
                                              (TODO: mettre à jour le lien)
                                              """
                                        ),
                                        ipywidgets.HTML("<hr/>Surface mobilisée :"),
                                        surface_output,
                                        surfacebutton,
                                        ipywidgets.HTML(
                                            "<hr/>Pour un ingrédient, renseignez « ingrédient » :"
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["landOccupation"],
                                                ),
                                                w_land_footprint,
                                            ),
                                        ),
                                        ipywidgets.HBox(
                                            (
                                                ipywidgets.Label(
                                                    FIELDS["scenario"],
                                                ),
                                                w_scenario,
                                            ),
                                        ),
                                        ipywidgets.Accordion(
                                            titles=[
                                                "Services écosystémiques : Ingrédients d'origine animale",
                                                "Services écosystémiques : Autres ingrédients",
                                            ],
                                            children=[
                                                ipywidgets.VBox(
                                                    [
                                                        ipywidgets.HBox(
                                                            (
                                                                ipywidgets.Label(
                                                                    FIELDS[
                                                                        "animalGroup1"
                                                                    ],
                                                                ),
                                                                w_animalGroup1,
                                                            ),
                                                        ),
                                                        ipywidgets.HBox(
                                                            (
                                                                ipywidgets.Label(
                                                                    FIELDS[
                                                                        "animalGroup2"
                                                                    ],
                                                                ),
                                                                w_animalGroup2,
                                                            ),
                                                        ),
                                                        ipywidgets.HBox(
                                                            (
                                                                ipywidgets.Label(
                                                                    FIELDS[
                                                                        "animalProduct"
                                                                    ],
                                                                ),
                                                                w_animalProduct,
                                                            ),
                                                        ),
                                                    ]
                                                ),
                                                ipywidgets.VBox(
                                                    [
                                                        ipywidgets.HBox(
                                                            (
                                                                ipywidgets.Label(
                                                                    FIELDS["cropGroup"],
                                                                ),
                                                                w_cropGroup,
                                                            ),
                                                        ),
                                                    ]
                                                ),
                                            ],
                                        ),
                                    ),
                                ),
                            ],
                        ),
                    )
                ),
                ipywidgets.VBox(
                    (ipywidgets.HTML("<h2>Fichier JSON résultant:</h2>"), file_output)
                ),
                ipywidgets.VBox(
                    [
                        ipywidgets.HTML(
                            f"""Si vous êtes satisfait(e) de vos modifications locales, vous devez
                          <b>publier</b> vos modifications, qui vont alors arriver dans la branche <a
                          style="color:blue"
                          href="https://github.com/MTES-MCT/ecobalyse/tree/{branch}">{branch}</a>
                          du dépôt Écobalyse.<br/> L'équipe Écobalyse pourra ensuite recalculer les
                          impacts et intégrer vos contributions."""
                        ),
                        ipywidgets.HBox((commitbutton, clear_git_button)),
                        git_output,
                    ]
                ),
                ipywidgets.VBox(
                    (
                        ipywidgets.HTML(
                            """
  <h2>Documentation de cet outil</h2> <ul>
                          """
                            """
  <li><b>Étape 1)</b> Cliquez sur le bouton « ▶▶ » dans la barre d'outils supérieure
  pour récupérer la dernière version de cet éditeur d'ingrédients. Si l'éditeur
  ne se recharge pas, patientez une ou deux minutes puis recommencez</li>
                          """
                            """
  <li><b>Étape 2)</b> Cliquez sur le sous-onglet « Liste », puis sélectionnez le
  Contributeur pour charger votre liste temporaire d'ingrédients. Vous pouvez
  annuler les changements temporaires et revenir à la liste publiée en cliquant
  sur le bouton vert « Réinitialiser ». </li>
                          """
                            """
  <li><b>Étape 3)</b> Ajouter un ingrédient :</li>
  Aller dans le sous-onglet « Formulaire » pour renseigner les caractéristiques
  de l’ingrédient à ajouter. <div style="padding-left: 50px">En utilisant
  l'explorateur depuis un autre onglet, il faut d'abord identifier l'ICV
  correspondant à l’ingrédient souhaité. Prenons l'exemple du sucre de canne. Par
  exemple l’ICV « Brown sugar, production, at plant {FR} U » semble être le plus
  adapté à l’ingrédient sucre de canne tel qu’il est utilisé en usine. Pour
  vérifier qu’il est bien fabriqué à partir de canne à sucre, le sous-onglet
  Technosphere de l'explorateur permet de vérifier les procédés qui entrent dans
  la composition de « Brown sugar, production, at plant {FR} U ». Il s’agit bien
  du procédé « Sugar, from sugarcane {RoW}| sugarcane processing, traditional
  annexed plant | Cut-off, S - Copied from Écoinvent U {RoW} ».</div> Après
  chaque ingrédient ajouté, cliquez sur « Enregistrer localement ». Réitérez
  cette étape pour chaque ingrédient.
                          """
                            """
  <li><b>Étape 4)</b> : Validez tous vos ingrédients ajoutés : allez sur l’onglet
  « Publier », et cliquez sur le bouton rouge une fois l’ensemble des
  modifications faites et les ingrédients ajoutés. Vos modifications arrivent sur
  la branche indiquée et pourra être vérifiée et intégrée en production dans
  Ecobalyse</li></ul>
                          """
                        ),
                    )
                ),
            ],
        ),
    )
    list_activities(w_filter.value)
    display_output_file()


savebutton.on_click(add_activity)
delbutton.on_click(delete_activity)
resetbutton.on_click(reset_activities)
clear_reset_button.on_click(clear_reset_output)
commitbutton.on_click(commit_activities)
clear_git_button.on_click(clear_git_output)
clear_save_button.on_click(clear_save_output)
uploadbutton.observe(upload_activities, names="value")
w_database.observe(changed_database_to(w_results), names="value")
w_search.observe(changed_search_to(w_results), names="value")
surfacebutton.on_click(compute_surface)

branch = current_branch()
list_activities(w_filter.value)
display(ipywidgets.HTML("<h1>Éditeur d'ingrédients</h1>"))
display(w_contributor)
display(main_output)
display_main()
