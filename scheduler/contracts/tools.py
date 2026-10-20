"""What the sandbox records and serves: corpus documents, the call log and the write log.
Every tool call is logged; every write is logged again, separately, so "invite sent" is
checked in the record of what happened, never in what an agent said."""
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CorpusDoc(BaseModel):
    """One external schedule in the frozen corpus, e.g. public holidays or a conference agenda."""
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    kind: Literal["public_holidays", "conference", "all_hands", "training", "fixtures", "other"]
    as_of: str                       # when this copy was taken
    source: str                      # where it came from ("fictional" for made-up documents)
    text: str


class Call(BaseModel):
    tool: str
    caller: str                      # "personal:p01", "coordinator", "gate", "harness"
    args: dict


class Write(BaseModel):
    tool: Literal["place_hold", "release_hold", "send_invite"]
    request_id: str
    start: str | None = None
    end: str | None = None
    key: str
    approval_id: str | None = None
