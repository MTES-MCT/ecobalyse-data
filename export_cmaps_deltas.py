#!/usr/bin/env python3
"""Export a CSV comparing impacts between the Wainstain CSV and processes_generic_impacts.json.
Also generate one stacked bar chart per ingredient for visual comparison."""

import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV_PATH = Path(
    "/Users/paulboosz/Downloads/Wainstain ingrédients transformés - data_3.csv"
)
PROC_PATH = Path(
    "/Users/paulboosz/src/ecobalyse-data/public/data/processes_generic_impacts.json"
)
OUT_PATH = Path("cmaps_impact_deltas.csv")
BASE_PLOTS_DIR = Path("cmaps_base_plots")
ACTIVITIES_PATH = Path("activities.json")
VISIBLE_THRESHOLD_PCT = 5.0

# Protected designation of origin (AOP/AOC/IGP/DOP/PDO) ingredients.
# An "Origine Inconnue" variant doesn't make sense for these — force visible=False
# regardless of delta_pct. Match against the base label (CMAPS label without the
# trailing " - FR"/"- OI"/"- OI BIO" suffix).
PROTECTED_ORIGIN_LABELS = {
    # French AOP cheeses
    "Beaufort",
    "Cantal. Salers ou Laguiole",
    "Chaource",
    "Comté",
    "Fourme d'Ambert",
    "Fromage bleu d'Auvergne",
    "Mont d'or ou Vacherin du Haut-Doubs (produit en France) ou Vacherin-Mont d'Or (produit en Suisse)",
    "Munster",
    "Pont l'Évêque",
    "Reblochon",
    "Roquefort",
    # French IGP cheese
    "Saint-Marcellin",
    # French / Swiss AOP-PDO cheese
    "Gruyère",
    # Italian DOP cheeses
    "Gorgonzola",
    "Parmesan",
}

IMPACT_COLS = [
    "CE _Climate_change",
    "CE_Acidification",
    "CE_Ecotox",
    "CE_fossil_use",
    "CE_eutrophisation_1",
    "CE_rayonnements",
    "CE_land_use",
    "CE_mineral_use",
    "CE_ozone_1",
    "CE_ozone_2",
    "CE_particules",
    "CE_eutrophisation_2",
    "CE_eutrophisation_3",
    "CE_water_use",
]

COMPLEMENT_COLS = [
    "CE_Crop_diversity",
    "CE_Hedges",
    "CE_Livestock_density",
    "CE_Permanent_pasture",
    "CE_Plot_size",
]

COMPLEMENT_MAP = {
    "CE_Crop_diversity": "cropDiversity",
    "CE_Hedges": "hedges",
    "CE_Livestock_density": "livestockDensity",
    "CE_Permanent_pasture": "permanentPasture",
    "CE_Plot_size": "plotSize",
}

# HYPOTHESIS: CMAPS swapped Climate change and Acidification columns
SHORT_NAMES = {
    "CE _Climate_change": "acd",  # swapped: CSV "Climate change" is actually Acidification
    "CE_Acidification": "cch",  # swapped: CSV "Acidification" is actually Climate change
    "CE_Ecotox": "etf-c",
    "CE_fossil_use": "fru",
    "CE_eutrophisation_1": "fwe",
    "CE_rayonnements": "ior",
    "CE_land_use": "ldu",
    "CE_mineral_use": "mru",
    "CE_ozone_1": "ozd",
    "CE_ozone_2": "pco",
    "CE_particules": "pma",
    "CE_eutrophisation_2": "swe",
    "CE_eutrophisation_3": "tre",
    "CE_water_use": "wtu",
}

# Labels for chart legend
CATEGORY_LABELS = [
    "Climate change",
    "Acidification",
    "Ecotoxicity",
    "Fossil use",
    "Eutro. freshwater",
    "Ionising radiation",
    "Land use",
    "Mineral use",
    "Ozone depletion",
    "Photochem. ozone",
    "Particulate matter",
    "Eutro. marine",
    "Eutro. terrestrial",
    "Water use",
    "Crop diversity",
    "Hedges",
    "Livestock density",
    "Permanent pasture",
    "Plot size",
]

CATEGORY_COLORS = [
    "#9025be",
    "#91cf4f",
    "#375622",
    "#9dc3e6",
    "#548235",
    "#be8f00",
    "#a9d18e",
    "#698ed0",
    "#ffc000",
    "#ff6161",
    "#ffc000",
    "#70ad47",
    "#c5e0b4",
    "#0070c0",
    "#d9a0c8",
    "#b5d99c",
    "#f0c27a",
    "#8db596",
    "#c4a35a",
]

IMPACTS_PATH = Path("impacts.json")


def load_ecoscore_factors():
    with open(IMPACTS_PATH) as f:
        impacts = json.load(f)
    factors = {}
    for trigram, info in impacts.items():
        eco = info.get("ecoscore")
        if eco and eco.get("normalization") and eco.get("weighting"):
            factors[trigram] = (eco["normalization"], eco["weighting"])
    return factors


ECOSCORE_FACTORS = load_ecoscore_factors()


def raw_to_upt(raw, trigram):
    f = ECOSCORE_FACTORS.get(trigram)
    if not f:
        return 0.0
    norm, weight = f
    return (raw / norm) * weight * 1_000_000


def strip_origin_suffix(label):
    return re.sub(r"\s*-\s*(FR|OI)(\s+BIO)?\s*$", "", label).strip()


def clean_display_name(base_label, origin, is_bio):
    name = re.sub(r"\.\s+", ", ", base_label).rstrip(". ")
    if origin == "FR":
        suffix = "FR BIO" if is_bio else "FR"
    else:
        suffix = "Origine Inconnue BIO" if is_bio else "Origine Inconnue"
    return f"{name} {suffix}"


def slugify(text):
    text = text.lower()
    text = text.replace("'", "").replace("\u2019", "")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text.strip("-")


def parse_float(val):
    val = val.strip().strip('"')
    if not val:
        return 0.0
    return float(val.replace(",", ""))


def make_grouped_stacked_bar_chart(base_label, variants, categories, colors, outpath):
    """Create a stacked bar chart grouping multiple variants side by side.
    variants: list of (variant_label, csv_values, proc_values).
    """
    n = len(variants)
    fig, ax = plt.subplots(figsize=(max(10, 3 * n + 4), 7))
    bar_width = 0.6
    group_spacing = 2.5
    positions = []
    xtick_positions = []
    xtick_labels = []

    for v_idx, (variant_label, csv_values, proc_values) in enumerate(variants):
        x_csv = v_idx * group_spacing
        x_proc = x_csv + 0.8
        positions.append((x_csv, x_proc))
        xtick_positions.extend([x_csv, x_proc])
        xtick_labels.extend([f"CMAPS\n{variant_label}", f"Ecobalyse\n{variant_label}"])

        csv_pos = [max(v, 0) for v in csv_values]
        csv_neg = [min(v, 0) for v in csv_values]
        proc_pos = [max(v, 0) for v in proc_values]
        proc_neg = [min(v, 0) for v in proc_values]

        csv_bottom_pos = 0
        proc_bottom_pos = 0
        csv_bottom_neg = 0
        proc_bottom_neg = 0

        for i, cat in enumerate(categories):
            color = colors[i % len(colors)]
            if csv_pos[i] > 0:
                ax.bar(
                    x_csv,
                    csv_pos[i],
                    bar_width,
                    bottom=csv_bottom_pos,
                    color=color,
                    edgecolor="white",
                    linewidth=0.3,
                )
                csv_bottom_pos += csv_pos[i]
            if csv_neg[i] < 0:
                ax.bar(
                    x_csv,
                    csv_neg[i],
                    bar_width,
                    bottom=csv_bottom_neg,
                    color=color,
                    edgecolor="white",
                    linewidth=0.3,
                )
                csv_bottom_neg += csv_neg[i]
            if proc_pos[i] > 0:
                ax.bar(
                    x_proc,
                    proc_pos[i],
                    bar_width,
                    bottom=proc_bottom_pos,
                    color=color,
                    edgecolor="white",
                    linewidth=0.3,
                )
                proc_bottom_pos += proc_pos[i]
            if proc_neg[i] < 0:
                ax.bar(
                    x_proc,
                    proc_neg[i],
                    bar_width,
                    bottom=proc_bottom_neg,
                    color=color,
                    edgecolor="white",
                    linewidth=0.3,
                )
                proc_bottom_neg += proc_neg[i]

        csv_total = sum(csv_values)
        proc_total = sum(proc_values)
        y_offset = max(csv_bottom_pos, proc_bottom_pos) * 0.02
        ax.text(
            x_csv,
            csv_bottom_pos + y_offset,
            f"{csv_total:.0f}",
            ha="center",
            fontsize=9,
            fontweight="bold",
        )
        ax.text(
            x_proc,
            proc_bottom_pos + y_offset,
            f"{proc_total:.0f}",
            ha="center",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_xticks(xtick_positions)
    ax.set_xticklabels(xtick_labels, fontsize=9)
    ax.set_ylabel("µPt", fontsize=11)
    ax.set_title(base_label, fontsize=13, fontweight="bold")
    ax.axhline(y=0, color="black", linewidth=0.5)

    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=colors[i % len(colors)], label=cat)
        for i, cat in enumerate(categories)
    ]
    ax.legend(
        handles=list(reversed(handles)),
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=8,
        frameon=False,
    )

    plt.tight_layout()
    fig.savefig(outpath, dpi=100, bbox_inches="tight")
    plt.close(fig)


def main():
    with open(PROC_PATH) as f:
        processes = json.load(f)
    proc_by_display = {}
    for p in processes:
        proc_by_display.setdefault(p.get("displayName", ""), []).append(p)

    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    BASE_PLOTS_DIR.mkdir(exist_ok=True)
    output_rows = []
    base_groups = {}

    for row in rows:
        label = row["label_product"].strip().strip('"')
        origin = row["Origine"].strip()
        is_bio = row["BIO"].strip() == "BIO"
        base_label = strip_origin_suffix(label)
        display_name = clean_display_name(base_label, origin, is_bio)

        procs = proc_by_display.get(display_name, [])
        if not procs:
            continue
        proc = procs[0]

        csv_ecs = parse_float(row.get("CE_PER_KILO", "0"))
        proc_ecs = proc.get("impacts", {}).get("ecs", 0) or 0
        delta_ecs = abs(csv_ecs - proc_ecs)
        denom = max(abs(csv_ecs), abs(proc_ecs), 0.01)
        delta_pct = abs(csv_ecs - proc_ecs) / denom * 100

        proc_impacts = proc.get("impacts", {})
        proc_compl = (
            proc.get("metadata", {}).get("complements", {})
            if proc.get("metadata")
            else {}
        )

        protected_oi = origin == "OI" and base_label in PROTECTED_ORIGIN_LABELS
        threshold_ok = delta_pct < VISIBLE_THRESHOLD_PCT
        visible = threshold_ok and not protected_oi

        out = {
            "label_product": label,
            "origin": origin,
            "bio": "BIO" if is_bio else "",
            "display_name": display_name,
            "visible": visible,
            "threshold_ok": threshold_ok,
            "protected_oi": protected_oi,
            "csv_ecs": round(csv_ecs, 2),
            "proc_ecs": round(proc_ecs, 2),
            "delta_ecs": round(delta_ecs, 2),
            "delta_pct": round(delta_pct, 1),
        }

        csv_values = []
        proc_values = []

        # 14 impact categories
        for col in IMPACT_COLS:
            tri = SHORT_NAMES[col]
            csv_val = round(parse_float(row.get(col, "0")), 2)
            raw = proc_impacts.get(tri, 0) or 0
            proc_val = round(raw_to_upt(raw, tri), 2)
            out[f"csv_{tri}"] = csv_val
            out[f"proc_{tri}"] = proc_val
            out[f"delta_{tri}"] = round(abs(csv_val - proc_val), 2)
            csv_values.append(csv_val)
            proc_values.append(proc_val)

        # 5 complements
        for col in COMPLEMENT_COLS:
            comp = COMPLEMENT_MAP[col]
            csv_val = round(parse_float(row.get(col, "0")), 2)
            proc_val = proc_compl.get(comp)
            proc_val = round(proc_val, 2) if proc_val is not None else 0.0
            out[f"csv_{comp}"] = csv_val
            out[f"proc_{comp}"] = proc_val
            out[f"delta_{comp}"] = round(abs(csv_val - proc_val), 2)
            csv_values.append(csv_val)
            proc_values.append(proc_val)

        output_rows.append(out)

        # Accumulate into base-product group for the grouped chart
        variant_tag = (
            ("FR" if origin == "FR" else "OI") + (" BIO" if is_bio else "")
        ).strip()
        base_slug = slugify(base_label)
        group = base_groups.setdefault(base_slug, {"label": base_label, "variants": []})
        group["variants"].append((variant_tag, csv_values, proc_values))

    # Sort by decreasing delta_pct
    output_rows.sort(key=lambda r: r["delta_pct"], reverse=True)

    if not output_rows:
        print("No rows to write")
        return

    fieldnames = list(output_rows[0].keys())
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Written {len(output_rows)} rows to {OUT_PATH}")

    # Update activities.json: visible decision is already computed per row
    visible_by_display = {r["display_name"]: r["visible"] for r in output_rows}
    protected_count = sum(1 for r in output_rows if r["protected_oi"])
    with open(ACTIVITIES_PATH) as f:
        activities = json.load(f)
    visible_count = hidden_count = touched = 0
    for activity in activities:
        for meta in activity.get("metadata", []) or []:
            display = meta.get("displayName")
            if display in visible_by_display:
                meta["visible"] = visible_by_display[display]
                touched += 1
                if meta["visible"]:
                    visible_count += 1
                else:
                    hidden_count += 1
    with open(ACTIVITIES_PATH, "w", encoding="utf-8") as f:
        json.dump(activities, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(
        f"Updated {touched} metadata entries in {ACTIVITIES_PATH}: "
        f"{visible_count} visible (<{VISIBLE_THRESHOLD_PCT}%), {hidden_count} hidden "
        f"(of which {protected_count} forced hidden by protected-origin rule)"
    )

    variant_order = {"FR": 0, "FR BIO": 1, "OI": 2, "OI BIO": 3}
    for base_slug, group in base_groups.items():
        variants = sorted(group["variants"], key=lambda v: variant_order.get(v[0], 99))
        plot_path = BASE_PLOTS_DIR / f"{base_slug}.png"
        make_grouped_stacked_bar_chart(
            group["label"], variants, CATEGORY_LABELS, CATEGORY_COLORS, plot_path
        )
    print(f"Generated {len(base_groups)} grouped plots in {BASE_PLOTS_DIR}/")


if __name__ == "__main__":
    main()
