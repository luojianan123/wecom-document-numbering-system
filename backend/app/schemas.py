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
    special_numbering: bool
    product_names: list[str] = Field(default_factory=list)
    board_names: list[str] = Field(default_factory=list)
    software_names: list[str] = Field(default_factory=list)
    created_at: datetime


class ProjectNumberRequestIn(BaseModel):
    project_code: str = Field(pattern=r"^\d{4}$")


class ProjectNumberRequestOut(BaseModel):
    id: int
    project_code: str
    requested_by_id: int
    requester_name: str
    requester_user_id: str
    status: Literal["pending", "processed"]
    created_at: datetime
    processed_at: datetime | None


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


class CodeClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claimant_name: str
    claimed_at: datetime


class BatchItemOut(BaseModel):
    id: int | None = None
    file_code_id: int | None = None
    original_name: str
    success: bool
    standard_name: str | None = None
    final_code: str | None = None
    error: str | None = None
    claims: list[CodeClaimOut] = Field(default_factory=list)


class ProjectInitOut(BaseModel):
    project: ProjectOut
    items: list[BatchItemOut]
    success_count: int
    failure_count: int


class GenerateCodeIn(BaseModel):
    project_id: int
    file_name: str = Field(min_length=1, max_length=512)


class NameReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    project: ProjectOut
    requested_by_id: int
    original_name: str
    proposed_standard_name: str | None
    issue_summary: str
    similar_names: list[dict[str, object]]
    status: Literal["pending", "approved", "rejected"]
    reviewed_name: str | None
    file_code_id: int | None
    file_code: FileCodeOut | None
    created_at: datetime
    reviewed_at: datetime | None


class GenerateCodeOut(BaseModel):
    status: Literal["generated", "existing", "pending_review"]
    message: str
    file_code: FileCodeOut | None = None
    review: NameReviewOut | None = None


class ApproveNameReviewIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=512)
    final_code: str | None = Field(default=None, min_length=1, max_length=64)


class SpecialNumberingIn(BaseModel):
    special_numbering: bool


class RejectNameReviewIn(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


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
    claimant_name: str
    claimed_at: datetime


class ComponentClaimOut(BaseModel):
    id: int
    claimant_name: str
    claimed_at: datetime


class ComponentNodeOut(BaseModel):
    id: int
    component_project_id: int
    parent_id: int | None
    kind: str
    name: str
    code: str
    stage: str
    sequence: int
    created_by_name: str
    claims: list[ComponentClaimOut] = Field(default_factory=list)


class ComponentProjectOut(BaseModel):
    id: int
    project_code: str
    product_type: Literal["machine", "structure", "hardware"]
    status: str
    created_at: datetime
    created_by_name: str
    nodes: list[ComponentNodeOut] = Field(default_factory=list)


class ComponentProjectSummaryOut(BaseModel):
    id: int
    project_code: str
    product_type: Literal["machine", "structure", "hardware"]
    status: str
    created_at: datetime
    created_by_name: str
    machine_count: int
    node_count: int
    claim_count: int


class ComponentProjectCreateIn(BaseModel):
    project_code: str = Field(pattern=r"^\d{4}$")
    machine_name: str | None = Field(default=None, min_length=1, max_length=256)
    product_type: Literal["machine", "structure", "hardware"] = "machine"
    is_prototype: bool = False
    stage: Literal["C", "M", "Z", "G"] | None = None


class ComponentMachineCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    is_prototype: bool = False
    stage: Literal["C", "M", "Z", "G"] | None = None


class ComponentNodeCreateIn(BaseModel):
    parent_id: int
    kind: Literal["component", "structure", "hardware", "software", "other", "part"]
    name: str = Field(min_length=1, max_length=256)
    is_prototype: bool = False
    stage: Literal["C", "M", "Z", "G"] | None = None


class ComponentNodeUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    code: str = Field(min_length=1, max_length=128)


class ComponentBulkDeleteIn(BaseModel):
    node_ids: list[int] = Field(min_length=1, max_length=2_000)


class ComponentDraftNodeIn(BaseModel):
    client_id: str = Field(min_length=1, max_length=64)
    parent_id: int | None = None
    parent_client_id: str | None = Field(default=None, min_length=1, max_length=64)
    kind: Literal["machine", "component", "structure", "hardware", "software", "other", "part"]
    name: str = Field(min_length=1, max_length=256)
    is_prototype: bool = False
    stage: Literal["C", "M", "Z", "G"] | None = None


class ComponentTreeGenerateIn(BaseModel):
    project_code: str = Field(pattern=r"^\d{4}$")
    product_type: Literal["machine", "structure", "hardware"] = "machine"
    nodes: list[ComponentDraftNodeIn] = Field(min_length=1, max_length=2_000)
