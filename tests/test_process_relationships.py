import json
import os

from rich.console import Console
from rich.table import Table


def load_json_file(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


def log_duplicate_processes(process_id_counts, process_id_items, processes, item_type):
    """Create a rich table to display duplicate process usage"""
    if not any(count > 1 for count in process_id_counts.values()):
        return

    table = Table(
        title=f"[yellow]⚠️  Duplicate Process Usage in {item_type}s.json[/yellow]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("ProcessId", style="cyan")
    table.add_column("Process Name", style="green")
    table.add_column("Count", justify="right", style="red")
    table.add_column("Used By", style="blue")

    for process_id, count in sorted(
        process_id_counts.items(), key=lambda x: x[1], reverse=True
    ):
        if count > 1:
            item_names = process_id_items[process_id]
            table.add_row(
                process_id,
                processes[process_id].get("name", "Unknown"),
                str(count),
                "\n".join(item_names),
            )

    console = Console()
    console.print(table)
    console.print()


def check_process_relationships(items, processes, item_type):
    """
    Check that each processId in items exists in processes and log warnings for duplicates.

    Args:
        items: List of items (ingredients or materials) containing processId
        processes: Dictionary of processes indexed by their id
        item_type: String describing the type of items ("ingredient" or "material")
    """
    # Check each item's processId
    for item in items:
        process_id = item.get("processId")
        if process_id is None:
            continue  # Skip items without processId

        # Verify that the processId exists in processes.json
        assert process_id in processes.keys(), (
            f"Process ID {process_id} from {item_type} {item.get('name', 'unknown')} not found in processes.json"
        )

    # Check that each processId is used only once
    process_id_counts = {}
    process_id_items = {}

    for item in items:
        process_id = item.get("processId")
        if process_id is None:
            continue
        process_id_counts[process_id] = process_id_counts.get(process_id, 0) + 1
        if process_id not in process_id_items:
            process_id_items[process_id] = []
        process_id_items[process_id].append(item.get("name", "unknown"))

    # Log duplicate process usage in a pretty table
    log_duplicate_processes(process_id_counts, process_id_items, processes, item_type)


def test_process_relationships():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load food processes for ingredients
    food_processes_path = os.path.join(
        base_dir, "public", "data", "food", "processes.json"
    )
    food_processes = {
        process["id"]: process for process in load_json_file(food_processes_path)
    }

    # Load textile processes for materials
    textile_processes_path = os.path.join(
        base_dir, "public", "data", "textile", "processes.json"
    )
    textile_processes = {
        process["id"]: process for process in load_json_file(textile_processes_path)
    }

    # Check ingredients against food processes
    ingredients_path = os.path.join(
        base_dir, "public", "data", "food", "ingredients.json"
    )
    ingredients = load_json_file(ingredients_path)
    check_process_relationships(ingredients, food_processes, "ingredient")

    # Check materials against textile processes
    materials_path = os.path.join(
        base_dir, "public", "data", "textile", "materials.json"
    )
    materials = load_json_file(materials_path)
    check_process_relationships(materials, textile_processes, "material")
