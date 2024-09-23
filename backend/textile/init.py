import json
from os import environ
from os.path import join

from textile.models import (
    Example,
    Material,
    Process,
    Product,
)


def init():
    """populate the db with initial public json data"""

    # PROCESSES
    if Process.objects.count() == 0:
        with open(
            join(
                environ.get("ECOBALYSE_PRIVATE_DIR"),
                "data",
                "textile",
                "processes_impacts.json",
            )
        ) as f:
            Process.objects.bulk_create([Process._fromJSON(p) for p in json.load(f)])
    else:
        print("Processes already loaded")

    # MATERIALS
    if Material.objects.count() == 0:
        with open(
            join(
                environ.get("ECOBALYSE_DIR"),
                "public",
                "data",
                "textile",
                "materials.json",
            )
        ) as f:
            materials = json.load(f)
            Material.objects.bulk_create([Material._fromJSON(m) for m in materials])
            # update with recursive FKs
            for material in materials:
                if material["recycledFrom"]:
                    m = Material.objects.get(pk=material["id"])
                    m.recycledFrom = Material.objects.get(pk=material["recycledFrom"])
                m.save()
    else:
        print("Materials already loaded")

    # PRODUCTS
    if Product.objects.count() == 0:
        with open(
            join(
                environ.get("ECOBALYSE_DIR"),
                "public",
                "data",
                "textile",
                "products.json",
            )
        ) as f:
            products = json.load(f)
            # product without FK
            Product.objects.bulk_create([Product._fromJSON(p) for p in products])
        for p in products:
            # update with FK
            Product.objects.get(pk=p["id"]).nonIroningProcessUuid = Process.objects.get(
                pk=p["use"]["nonIroningProcessUuid"]
            )
    else:
        print("Products already loaded")

    # EXAMPLES
    if Example.objects.count() == 0:
        with open(
            join(
                environ.get("ECOBALYSE_DIR"),
                "public",
                "data",
                "textile",
                "examples.json",
            )
        ) as f:
            examples = json.load(f)
            # all fields except the m2m
            Example.objects.bulk_create([Example._fromJSON(e) for e in examples])
            # create the m2m intermediary records
            for e in examples:
                for s in e["query"]["materials"]:
                    Example.objects.get(pk=e["id"]).add_material(s)
            Example
    else:
        print("Examples already loaded")