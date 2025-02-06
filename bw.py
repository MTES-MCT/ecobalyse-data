from pprint import pprint

import bw2calc
import bw2data

from common.impacts import impacts as impacts_py
import sys

bw2data.projects.set_current("ecobalyse")
# print(bw2data.databases)
# db = bw2data.Database("Ecobalyse")
# db = bw2data.Database("WFLDB")
# db = bw2data.Database("Ecoinvent 3.9.1")
# db = bw2data.Database("Ecoinvent 3.10")
db = bw2data.Database("Agribalyse 3.1.1")
# db = bw2data.Database("Ecobalyse")
# db = bw2data.Database("biosphere3")
#
# objs = [obj for obj in db if obj.get("type") == "emission"]
# all_objs = [obj for obj in db]
# print(f"Total number of biosphere objs {len(all_objs)}")
# print(f"Number of biosphere objs with type == 'emission': {len(objs)}")
# pprint(all_objs)
# import sys
#
# sys.exit(0)

for obj in db:
    t = obj.get("name")
    if t == "Agave tequilana, at farm {MX} U":
        print(t)
        from pprint import pp

        pp(obj)
        pp(obj.as_dict())

        for exc in (
            obj.exchanges()
        ):  # or this, visualize all exchanges of an activity and specific attributes
            print(exc)
            print(exc["type"])
            print(f"Input : {exc['input']}")
            print(f"Output : {exc['output']}")
            print(exc["input"][0])
            print(exc["input"][1])
            print(exc.input)
            print(exc.as_dict())
            print("-------")
sys.exit(0)

activity = db.get("4a9ea0a29fbde60e2d1fc5c33d8a4f3a")
print(activity)


results = dict()
lca = bw2calc.LCA({activity: 1})
lca.lci()
for key, method in impacts_py.items():
    lca.switch_method(method)
    lca.lcia()
    # print("characterized_inventory\n", lca.characterized_inventory)
    results[key] = float("{:.10g}".format(lca.score))
    print(f"{activity}  {key}: {lca.score}")

import sys

sys.exit(0)

print("## -> Search")
# activity = db.search(
#     "electricity production, natural gas, combined cycle power plant IN"
# )[0]


all_objs = [obj for obj in bw2data.Database("Agribalyse 3.1.1")]

for obj in all_objs:
    t = obj.get("type")
    print(t)
    if obj.get("type", "process") == "process":
        print("-> process")
        print(obj)


sys.exit(0)
activity = db.search("Carrot, organic 2023, national average, at farm gate {FR} U")[0]
pprint(activity)

print("## -> Get methods")
for method in bw2data.methods:
    if (
        method[0] == "Environmental Footprint 3.1 (adapted) patch wtu"
        and method[1] == "Climate change"
    ):
        print(f"-> Method {method} {type(method)}")

        for line in bw2data.Method(method):
            a = line[0]
            name = a.get("name")

            if "carbon dioxide, fossil" in name.lower():
                print(f"-> Activity name {name}")
                print(a)

            # if line and len(line) > 0 and not isinstance(line[0], int):
            # substance = tuple(line[0])
            # if substance[1] == "aa7cac3a-3625-41d4-bc54-33e2cf11ec46":
            #     print(line)
            #     print(substance)


print("")
print(f"## -> Biosphere for {activity}")
bio = activity.biosphere()
print(f"## -> {type(bio)} - {len(bio)}")

# for exchange in bio:
#     print(str(exchange.input))
#     print(type(exchange))
#
#     if exchange.input.get("name") == "Carbon dioxide, fossil":
#         pprint(f"Ex: {exchange}")
#         print(exchange.input[0])
#         print(exchange.input[1])
#         print(f"-> Input amount {exchange.input.get('amount')}")
#         print(f"-> Input unit {exchange.input.get('unit')}")
#
#         print(exchange.output[0])
#         print(exchange.output[1])
#         print(f"-> Output amount {exchange.output.get('amount')}")
#         print(f"-> Output unit {exchange.output.get('unit')}")

tech = activity.technosphere()

print("")
print(f"## -> Technosphere for {activity}")
print(f"## -> {type(tech)} - {len(tech)}")
# for exchange in tech:
#     pprint(f"Ex: {exchange}")
#     print(exchange.input[0])
#     print(exchange.input[1])
#     print(f"-> Input amount {exchange.input.get('amount')}")
#     print(f"-> Input unit {exchange.input.get('unit')}")
#
#     print(exchange.output[0])
#     print(exchange.output[1])
#     print(f"-> Output amount {exchange.output.get('amount')}")
#     print(f"-> Output unit {exchange.output.get('unit')}")


prod = activity.production()
print("")
print(f"## -> Production for {activity}")
print(f"## -> {type(prod)} - {len(prod)}")
for p in prod:
    print(f"-> Prod {p.amount}")
