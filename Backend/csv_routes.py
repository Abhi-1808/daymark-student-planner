"""Download manual organizer data and upload bounded UTF-8 CSV files."""

import io
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from .conflict_routes import event_save_lock
from .csv_io import CSVError, MAX_BYTES, csv_chunks, parse_rows
from .database import get_db
from .item_payloads import ManualItemPayload
from .manual_items import add_manual_item
from .models import Item, ItemSource

router = APIRouter(tags=["CSV files"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/api/items/export.csv")
def export_csv(db: Db):
    # Load while the dependency session is alive; stream encoding afterwards.
    items = list(db.scalars(select(Item).where(Item.source == ItemSource.MANUAL, Item.duplicate_of_id.is_(None)).order_by(Item.id)))
    return StreamingResponse(csv_chunks(items), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="daymark-manual-items.csv"'})


def import_csv_text(db, text):
    try:
        parsed = parse_rows(io.StringIO(text))
    except CSVError as error:
        raise HTTPException(400, str(error)) from None
    errors = list(parsed.errors)
    imported = 0
    with event_save_lock:
        for row_number, payload in parsed.rows:
            manual = ManualItemPayload.model_validate(payload.model_dump(exclude_unset=True))
            try:
                add_manual_item(db, manual)
                imported += 1
            except HTTPException as error:
                if error.status_code != 409:
                    raise
                errors.append({"row": row_number, "message": "This event overlaps your schedule. Review it in the event editor before adding it."})
        db.commit()
    return {"imported": imported, "skipped": parsed.total - imported, "errors": sorted(errors, key=lambda row: row["row"])}


@router.post("/api/items/import")
async def import_csv(request: Request, db: Db):
    if request.headers.get("content-type", "").split(";")[0].strip().lower() not in ("text/csv", "application/csv", "text/plain", "application/octet-stream"):
        raise HTTPException(415, "Upload the CSV file as a text/csv request body.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "CSV files must be at most 2 MiB.")
        data.extend(chunk)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Save the CSV file with UTF-8 encoding.") from None
    return await run_in_threadpool(import_csv_text, db, text)
