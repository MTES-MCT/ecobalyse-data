#!/usr/bin/env python
# coding: utf-8

"""Vérification des exports de la base Agribalyse.

Paramètres positionnels optionnels : le nom du fichier products.json et processes.json à utiliser.
Exemple :
    python checks.py products_EF2.json processes_EF2.json

"""

from collections import defaultdict
import copy
import csv
import json
import re
import sys
from impacts import impacts_to_synthese

THRESHOLD = 4  # en pourcentage : 10 -> 10%


def check_missing_steps(products):
    """Nombre de produits qui n'ont pas 5 étapes."""
    count = 0
    for key, product in products.items():
        for step_key, step in product.items():
            if step == {}:
                count += 1
                print(f"{key} has no {step_key}")
    return count


def check_ciqual_impacts(processes, synthese_filename):
    """Liste des différences d'impact entre la synthèse agribalyse et les exports json."""
    ciqual_code_regex = re.compile(r"\[Ciqual code: (\d+)\]")

    processes_to_ciqual = {}
    for process in processes:
        match = re.search(ciqual_code_regex, process)
        if match:
            ciqual_code = match[1]
            processes_to_ciqual[ciqual_code] = processes[process]

    with open(synthese_filename) as csvfile:
        reader = csv.DictReader(csvfile)
        count = 0
        for row in reader:
            ciqual_code = row["Code CIQUAL"]
            for (impact, (trigram, multiplier)) in impacts_to_synthese.items():
                impact_a = float(row[impact]) * multiplier
                impact_b = processes_to_ciqual[ciqual_code]["impacts"][trigram]
                diff = get_diff(impact_a, impact_b)
                if diff:
                    count += 1
                    print(
                        f"{ciqual_code} (impact {trigram}), diff: {round(diff * 100 / abs(max(impact_a, impact_b)))}% - json: {impact_b}, synthèse: {impact_a}"
                    )
        return count


def get_diff(impact_a, impact_b):
    max_impact = max(impact_a, impact_b)
    min_impact = min(impact_a, impact_b)
    diff = max_impact - min_impact
    threshold = abs(max_impact) * THRESHOLD / 100
    if diff > threshold:
        return diff


def processes_for_step(step):
    """Liste de tous les process d'une étape."""
    processes = []
    for (_, category) in step.items():
        processes += category
    return processes


def check_impact_diff_consumer(products, processes):
    """Différence entre les impacts globaux et la somme des sous-impacts menant à l'étape consommation."""
    count = 0

    for key, product in products.items():
        count += get_impacts_diff(processes, key, 1, product["consumer"])
    return count


def check_impact_diff_supermarket(products, processes):
    """Différence entre les impacts globaux et la somme des sous-impacts menant à l'étape supermarché."""
    count = 0

    for key, product in products.items():
        # Get the main item from the step just above
        (mainProcessName, amount) = get_main_item(products[key], "consumer")
        count += get_impacts_diff(
            processes, mainProcessName, amount, product["supermarket"]
        )

    return count


def check_impact_diff_distribution(products, processes):
    """Différence entre les impacts globaux et la somme des sous-impacts menant à l'étape stockage."""
    count = 0

    for key, product in products.items():
        # Get the main item from the step just above
        (mainProcessName, amount) = get_main_item(products[key], "supermarket")
        count += get_impacts_diff(
            processes, mainProcessName, amount, product["distribution"]
        )

    return count


def check_impact_diff_packaging(products, processes):
    """Différence entre les impacts globaux et la somme des sous-impacts menant à l'étape packaging."""
    count = 0

    for key, product in products.items():
        # Get the main item from the step just above
        (mainProcessName, amount) = get_main_item(products[key], "distribution")
        count += get_impacts_diff(
            processes, mainProcessName, amount, product["packaging"]
        )

    return count


def check_impact_diff_plant(products, processes):
    """Différence entre les impacts globaux et la somme des sous-impacts menant à l'étape fabrication."""
    count = 0

    for key, product in products.items():
        # Get the main item from the step just above
        (mainProcessName, amount) = get_main_item(products[key], "packaging")
        count += get_impacts_diff(processes, mainProcessName, amount, product["plant"])

    return count


def get_main_item(product, step):
    """Renvoie le processus principal (qu'on utilise pour construire l'arbre) d'une étape ainsi que sa quantité."""
    for process in processes_for_step(product[step]):
        if process["mainProcess"]:
            return process["processName"], process["amount"]
    else:
        # We didn't find a main process at this step (!), return the first process
        assert (
            False
        ), f"We didn't find a main process at step {step} for product {product}"


def get_impacts_diff(processes, mainProcessName, amount, step):
    """Affiche les écarts d'impact supérieur à THRESHOLD."""
    count = 0
    sum_impacts = defaultdict(int)
    mainProcess = processes[mainProcessName]
    for ingredient in processes_for_step(step):
        processName = ingredient["processName"]
        for impact in mainProcess["impacts"].keys():
            sum_impacts[impact] += (
                processes[processName]["impacts"][impact] * ingredient["amount"]
            )

    for impact in mainProcess["impacts"].keys():
        diff = get_diff(
            sum_impacts[impact],
            # The sum of sub impacts is for the amount of "main process" requested for this product.
            processes[mainProcessName]["impacts"][impact] * amount,
        )
        if diff:
            count += 1
            percentage = (
                diff
                * 100
                / abs(
                    max(
                        sum_impacts[impact],
                        processes[mainProcessName]["impacts"][impact] * amount,
                    )
                )
            )
            print(
                f"{mainProcessName} (impact {impact}), diff: {round(percentage)}% - global: {processes[mainProcessName]['impacts'][impact] * amount}, somme: {sum_impacts[impact]}"
            )
    return count


def read_json(filename):
    with open(filename, "r") as infile:
        return json.load(infile)


if __name__ == "__main__":
    products_filename = "products.json"
    processes_filename = "processes.json"
    if len(sys.argv) == 3:
        products_filename = sys.argv[1]
        processes_filename = sys.argv[2]
    products = read_json(products_filename)
    processes = read_json(processes_filename)

    print(">>> Liste des produits avec étapes manquantes")
    count = check_missing_steps(products)
    print(f"{count} missing steps")

    print()

    print(
        f">>> Liste des différences d'impact supérieures à {THRESHOLD}% entre l'export et la synthèse Agribalyse"
    )
    count = check_ciqual_impacts(processes, "../Agribalyse_Synthese.csv")
    print(f"Total de {count} impacts qui ont une différence supérieure à {THRESHOLD}%")

    print()

    print(
        f">>> Liste des differences d'impact supérieures à {THRESHOLD}% entre l'impact global et la somme des impacts des composants 'at consumer'"
    )
    count = check_impact_diff_consumer(products, processes)
    print(
        f"Total de {count} impacts qui ont une différence supérieure à {THRESHOLD}% à l'étape consumer"
    )

    print()

    print(
        f">>> Liste des differences d'impact supérieures à {THRESHOLD}% entre l'impact global et la somme des impacts des composants 'at supermarket'"
    )
    count = check_impact_diff_supermarket(products, processes)
    print(
        f"Total de {count} impacts qui ont une différence supérieure à {THRESHOLD}% à l'étape supermarket"
    )

    print()

    print(
        f">>> Liste des differences d'impact supérieures à {THRESHOLD}% entre l'impact global et la somme des impacts des composants 'at distribution'"
    )
    count = check_impact_diff_distribution(products, processes)
    print(
        f"Total de {count} impacts qui ont une différence supérieure à {THRESHOLD}% à l'étape distribution"
    )

    print()

    print(
        f">>> Liste des differences d'impact supérieures à {THRESHOLD}% entre l'impact global et la somme des impacts des composants 'at packaging'"
    )
    count = check_impact_diff_packaging(products, processes)
    print(
        f"Total de {count} impacts qui ont une différence supérieure à {THRESHOLD}% à l'étape packaging"
    )

    print()

    print(
        f">>> Liste des differences d'impact supérieures à {THRESHOLD}% entre l'impact global et la somme des impacts des composants 'at plant'"
    )
    count = check_impact_diff_plant(products, processes)
    print(
        f"Total de {count} impacts qui ont une différence supérieure à {THRESHOLD}% à l'étape plant"
    )
