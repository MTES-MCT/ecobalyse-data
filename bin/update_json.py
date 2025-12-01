import argparse
import json

from rich.console import Console
from rich.table import Table

from ecobalyse_data.detect import (
    cooked_to_raw,
    density,
    metadata,
    scenario,
)

# selection of modules that can update the json
UPDATE_MODULES = {
    "density": density,
    "scenario": scenario,
    "cooked_to_raw": cooked_to_raw,
    "metadata": metadata,
}

if __name__ == "__main__":
    description = (
        "This script updates the JSON list of ingredient objects with computed metadata"
    )
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", type=argparse.FileType("r"), help="Input JSON file")
    parser.add_argument("output", type=argparse.FileType("w"), help="Output JSON file")
    parser.add_argument(
        "--what",
        required=True,
        choices=list(UPDATE_MODULES.keys()) + ["all"],
        help="What to update",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Minimum similarity score to accept match",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Include best match and score in output JSON",
    )
    args = parser.parse_args()

    json_data = json.load(args.input)
    # launch the update function of the module for each metadata to update
    for module_name in UPDATE_MODULES.keys() if args.what == "all" else [args.what]:
        module = UPDATE_MODULES[module_name]
        threshold = args.threshold if args.threshold is not None else module.THRESHOLD
        json_data = module.update(
            json_data,
            threshold=threshold,
            debug=args.debug,
        )
        if args.debug:
            console = Console()
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Food")
            table.add_column("Translated")
            table.add_column(module_name)
            table.add_column("Best match")
            table.add_column("Similarity")
            for obj in json_data:
                score = obj.get(module.SCORE_KEY)
                color = (
                    "red"
                    if score <= module.BAD
                    else "white"
                    if score >= module.GOOD
                    else "yellow"
                )
                table.add_row(
                    module._name(obj),
                    obj["TRANSLATED"],
                    f"{module._get(obj)}",
                    obj.get(module.MATCH_KEY),
                    f"[{color}]{score:.2f}[/{color}]",
                )
            mean = sum(s := [i[module.SCORE_KEY] for i in json_data]) / len(s)
            table.add_row("", "", "⚠️  Mean of all scores", f"{mean:.2f}")
            console.print(table)

        # save the output file
        args.output.write(json.dumps(json_data, indent=2, ensure_ascii=False))
        print(f"✅ Updated {len(json_data)} ingredients")
