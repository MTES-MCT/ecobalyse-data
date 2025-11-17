import argparse
import json

from ecobalyse_data.detect import density, scenario

# selection of modules that can update the json
UPDATE_MODULES = {"density": density, "scenario": scenario}


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
    for module in UPDATE_MODULES.keys() if args.what == "all" else [args.what]:
        module = UPDATE_MODULES[module]
        threshold = args.threshold if args.threshold is not None else module.THRESHOLD
        json_data = module.update(
            json_data,
            threshold=threshold,
            debug=args.debug,
        )

        # save the output file
        args.output.write(json.dumps(json_data, indent=2, ensure_ascii=False))
        print(f"✅ Updated {len(json_data)} ingredients")
