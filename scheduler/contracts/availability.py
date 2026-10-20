"""The availability summary: the only thing a personal agent sends the coordinator agent.
It says *when* a participant can meet, never *why*: there is no field for a reason, a title
or free text, and any extra key is rejected."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from scheduler.timegrid import Moment

Status = Literal["available", "prefer_not", "unavailable"]


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: Moment
    end: Moment


class SlotStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: Moment
    end: Moment
    status: Status
    weight: float = 0.0          # how strongly "prefer_not"; 0-1
    relaxable: bool = False      # "unavailable", but could be freed with the participant's consent

    @model_validator(mode="after")
    def check_fields(self):
        if self.status != "prefer_not" and self.weight:
            raise ValueError("weight is only for prefer_not")
        if not 0 <= self.weight <= 1:
            raise ValueError("weight must be between 0 and 1")
        if self.status != "unavailable" and self.relaxable:
            raise ValueError("relaxable is only for unavailable")
        return self


class AvailabilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant_id: str
    request_id: str
    slots: list[SlotStatus]
    unknown: list[Window] = []   # windows the personal agent could not resolve: never free

    def status_of(self, start: str) -> SlotStatus | None:
        return next((s for s in self.slots if s.start == start), None)
