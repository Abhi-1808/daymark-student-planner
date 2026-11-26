from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

DateText = str
Color = Literal["teal", "blue", "violet", "amber", "rose"]


def as_day(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Use YYYY-MM-DD for dates")
    return parsed


def as_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if "T" not in value or parsed.tzinfo is None:
        raise ValueError("Timed events require an ISO date and time with an offset")
    return parsed


def canonical(value: str) -> str:
    if len(value) == 10:
        return as_day(value).isoformat()
    return as_time(value).astimezone(timezone.utc).isoformat(timespec="milliseconds")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Record(Input):
    kind: Literal["event", "task", "course", "attendance"]
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=10000)
    course: str = Field(default="", max_length=80)
    category: Literal["class", "exam", "study", "personal", "holiday", "assignment"] = "personal"
    color: Color = "teal"
    start: DateText | None = None
    end: DateText | None = None
    due: DateText | None = None
    location: str = Field(default="", max_length=200)
    priority: Literal["low", "normal", "high"] = "normal"
    done: bool = False
    repeat: Literal["none", "daily", "weekly"] = "none"
    repeat_until: DateText | None = None
    skip_days: list[DateText] = Field(default_factory=list, max_length=366)
    completed_days: list[DateText] = Field(default_factory=list, max_length=1000)
    attendance: Literal["present", "absent", "excused"] = "present"
    minutes: int = Field(default=60, ge=15, le=480)
    target: int = Field(default=75, ge=1, le=100)
    busy: bool = True
    reminder: int | None = Field(default=None, ge=0, le=1440)
    parent: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def dates_match(self):
        if self.kind == "event":
            if not self.start or not self.end or (len(self.start) == 10) != (len(self.end) == 10):
                raise ValueError("Events need matching start and end date types")
            self.start, self.end = canonical(self.start), canonical(self.end)
            if self.start >= self.end:
                raise ValueError("End must follow start")
        if self.due:
            as_day(self.due)
        if self.kind == "attendance" and (not self.due or not self.course):
            raise ValueError("Attendance needs a date and subject code")
        if self.repeat_until:
            as_day(self.repeat_until)
            if self.repeat_until < (self.due or (self.start if self.start and len(self.start) == 10 else "")):
                raise ValueError("Repeat end must follow the first day")
        if self.repeat != "none" and self.kind == "task" and not self.due:
            raise ValueError("Repeating tasks need a due date")
        for value in self.skip_days + self.completed_days:
            as_day(value)
        return self


class Preferences(Input):
    name: str = Field(default="Student", min_length=1, max_length=60)
    timezone: str = "Asia/Kolkata"
    buffer: int = Field(default=10, ge=0, le=90)
    day_start: int = Field(default=8, ge=0, le=23)
    day_end: int = Field(default=21, ge=1, le=24)

    @model_validator(mode="after")
    def valid_settings(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Enter a valid IANA time zone, such as Asia/Kolkata") from error
        if self.day_end <= self.day_start:
            raise ValueError("Planning hours must end after they start")
        return self
