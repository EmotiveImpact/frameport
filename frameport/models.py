from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, JsonValue, model_validator
import json

VIEWPORTS = [390, 540, 768, 1024, 1440]

class BridgeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_version: Literal["frameport.bridge.v1"] = Field(alias="schema")
    publishedUrl: str = Field(max_length=2048)
    project: dict[str, JsonValue] = Field(default_factory=dict)
    nodes: list[dict[str, JsonValue]] = Field(default_factory=list, max_length=7000)
    collections: list[dict[str, JsonValue]] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def size_limit(self):
        if len(json.dumps(self.model_dump(), ensure_ascii=False).encode()) > 1_000_000:
            raise ValueError("The project manifest exceeds 1 MB.")
        return self

class ConvertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(default="", max_length=2048)
    name: str = Field(default="", max_length=80)
    permission: bool = False
    demo: bool = False
    crawl: bool = True
    max_pages: int = Field(default=3, ge=1, le=8)
    format: Literal["react", "html", "both"] = "both"
    bridge: BridgeManifest | None = None

class TextPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(max_length=5000)

class EditRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    model_config = ConfigDict(extra="forbid")
    patches: list[TextPatch] = Field(min_length=1, max_length=200)

class Issue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    page: str = ""
    count: int = 1

class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=256)

class RenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
