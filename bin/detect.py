import argparse

from rich.console import Console
from rich.table import Table

from ecobalyse_data.detect import UPDATE_MODULES

if __name__ == "__main__":
    description = (
        "This script updates the JSON list of ingredient objects with computed metadata"
    )
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", type=argparse.FileType("r"), help="Input JSON file")
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
        help="Include best match and score in output",
    )
    args = parser.parse_args()

    input_text = args.input
    # launch the update function of the module for each metadata to update
    for module_name in UPDATE_MODULES.keys() if args.what == "all" else [args.what]:
        module = UPDATE_MODULES[module_name]
        threshold = args.threshold if args.threshold is not None else module.THRESHOLD
        value, score, best_match, translated = module.detect(
            input_text,
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
            color = (
                "red"
                if score <= module.BAD
                else "white"
                if score >= module.GOOD
                else "yellow"
            )
            table.add_row(
                input_text,
                translated,
                "",
                best_match,
                f"[{color}]{score:.2f}[/{color}]",
            )
            console.print(table)
