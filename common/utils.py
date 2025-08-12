"""
Common utility functions used across the project.
"""

import uuid


def validate_id(id: str) -> str:
    """
    Validate that an ID is lowercase and does not contain spaces.

    Args:
        id: The ID string to validate

    Returns:
        str: The validated ID

    Raises:
        ValueError: If the ID is not lowercase or contains spaces
    """
    # Check the id is lowercase and does not contain space
    if id.lower() != id or id.replace(" ", "") != id:
        raise ValueError(f"This identifier is not lowercase or contains spaces: {id}")
    return id


def get_activity_key(eco_activity, bw_activity):
    """
    Extract the key for activity objects. This is the key used to create the process id and deduplicate activities.

    Args:
        eco_activity: Ecobalyse activity object
        bw_activity: Brightway activity object

    Returns:
        str: The key of the activity
    """

    # Trying multiple possible way to get the name because we don't always have the bw_activity.name (for example : when source = Custom)
    activity_name = bw_activity.get(
        "name", eco_activity.get("displayName", eco_activity.get("name"))
    )
    activity_location = bw_activity.get("location", "")
    return f"{eco_activity.get('source')}:{activity_name}:{activity_location}"


def get_process_id(eco_activity, bw_activity) -> uuid.UUID:
    """Generates a unique UUID v5 based on the activity key

    Args:
        eco_activity: Ecobalyse activity object
        bw_activity: Brightway activity object

    Returns:
        uuid: The process id of the activity
    """
    return uuid.uuid5(uuid.NAMESPACE_DNS, get_activity_key(eco_activity, bw_activity))
