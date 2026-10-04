def dynamic_fefo_sort(components):
    """
    Sorts components by least dynamic remaining days (First Expired, First Out).
    Ties broken deterministically by nominal_stored_days descending, then batch_id.
    """
    return sorted(
        components,
        key=lambda c: (
            c.get("dynamic_remaining_days", c.get("effective_remaining_days", c.get("remainingDays", float("inf")))),
            -c.get("nominal_stored_days", c.get("storedDays", 0)),
            c.get("batch_id", c.get("batchId", "")),
        ),
    )


def prioritize_fefo(lifecycle_results):
    """
    Prioritizes components based on the least remaining shelf life.
    First Expired, First Out (FEFO).
    Supports standard linear results ('remainingDays') as well as dynamic
    Arrhenius degradation results ('dynamic_remaining_days' / 'effective_remaining_days').
    """
    valid_components = []

    for component in lifecycle_results:
        if (
            ("dynamic_remaining_days" in component and component["dynamic_remaining_days"] is not None)
            or ("effective_remaining_days" in component and component["effective_remaining_days"] is not None)
            or ("remainingDays" in component and component["remainingDays"] is not None)
        ):
            valid_components.append(component)

    sorted_components = sorted(
        valid_components,
        key=lambda c: (
            c.get("dynamic_remaining_days", c.get("effective_remaining_days", c.get("remainingDays"))),
            -c.get("nominal_stored_days", c.get("storedDays", 0)),
            c.get("batch_id", c.get("batchId", "")),
        ),
    )

    return sorted_components