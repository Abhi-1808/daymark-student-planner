"""Shared create-only persistence for manual entries and validated CSV rows."""

import json
from .conflict_routes import check_manual_event
from .models import Item, ItemSource


def add_manual_item(db, payload, default_priority=None):
    check_manual_event(db, payload)
    values = payload.model_dump(exclude={"allow_conflict"})
    if default_priority is not None and "priority" not in payload.model_fields_set:
        values["priority"] = default_priority
    values["subtasks"] = json.dumps(values["subtasks"])
    item = Item(source=ItemSource.MANUAL, **values)
    db.add(item)
    db.flush()
    return item
