"""Explicit provider dispatch; unknown sources must not inherit LMS settings."""

from .models import ItemSource
from .sync import SyncError


def resolve_source_configuration(source, *, google, camu, lms, outlook=None):
    if source in (ItemSource.GOOGLE_CAL, ItemSource.GOOGLE_TASKS):
        return google()
    if source is ItemSource.CAMO:
        return camu()
    if source is ItemSource.LMS:
        return lms()
    if source is ItemSource.OUTLOOK and outlook:
        return outlook()
    raise SyncError("This source does not support syncing.", 400)
