from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wecom_user_id: str
    name: str
    role: Literal["user", "admin"]


class MeOut(BaseModel):
    authenticated: bool = True
    user: UserOut
    csrf_token: str
    auth_mode: Literal["mock", "live"]


class DevLoginIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    role: Literal["user", "admin"] = "user"


class AuthStartOut(BaseModel):
    mode: Literal["mock", "live"]
    authorization_url: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_code: str
    project_name: str
    status: str
    created_at: datetime


class FileCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    original_name: str
    standard_name: str
    segment_a: str
    segment_b: str
    segment_c: str
    segment_d: str
    segment_e: str
    segment_f: str
    segment_g: str
    segment_h: str
    final_code: str
    source: str
    enabled: bool


class BatchItemOut(BaseModel):
    id: int | None = None
    file_code_id: int | None = None
    original_name: str
    success: bool
    standard_name: str | None = None
    final_code: str | None = None
    error: str | None = None


class ProjectInitOut(BaseModel):
    project: ProjectOut
    items: list[BatchItemOut]
    success_count: int
    failure_count: int


class GenerateCodeIn(BaseModel):
    project_id: int
    file_name: str = Field(min_length=1, max_length=512)


class RetryCodeIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)


class ManualCodeIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)
    final_code: str = Field(min_length=1, max_length=64)


class BatchDeleteIn(BaseModel):
    file_code_ids: list[int] = Field(default_factory=list, max_length=2_000)
    batch_item_ids: list[int] = Field(default_factory=list, max_length=2_000)


class ClaimOut(BaseModel):
    file_code: FileCodeOut
    claimed_at: datetime
