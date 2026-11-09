"""Map imported records and prune the authoritative MyCamu window separately."""

from datetime import datetime

from sqlalchemy import delete, select

from .models import Item, ItemSource, ItemStatus, ItemType


def upsert_external_items(db, source, external_items, priority_for_due, *, synced_at=None):
    imported, updated = 0, 0
    synced_at = synced_at or datetime.utcnow()
    for external in external_items:
        item = db.scalar(select(Item).where(Item.source == source, Item.source_id == external.source_id))
        values = {
            "type": external.type, "title": external.title, "description": external.description,
            "start": external.start, "end": external.end, "due": external.due,
            "status": external.status, "last_synced": synced_at,
        }
        if item is None:
            db.add(Item(**values, priority=priority_for_due(external.due), source=source, source_id=external.source_id))
            imported += 1
        else:
            for key, value in values.items():
                if key == "status" and value is ItemStatus.PENDING and item.status is ItemStatus.DONE:
                    continue
                setattr(item, key, value)
            updated += 1
    return imported, updated


def prune_camu_window(db, source_ids, window_start, window_end):
    db.execute(delete(Item).where(
        Item.source == ItemSource.CAMO,
        Item.type == ItemType.EVENT,
        Item.start >= window_start,
        Item.start < window_end,
        Item.source_id.not_in(source_ids),
    ))
