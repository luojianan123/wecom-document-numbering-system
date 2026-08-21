from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    wecom_user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="user")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="creator")
    claims: Mapped[list["CodeClaim"]] = relationship(back_populates="user")
    name_review_requests: Mapped[list["NameReviewRequest"]] = relationship(
        back_populates="requester",
        foreign_keys="NameReviewRequest.requested_by_id",
    )
    project_number_requests: Mapped[list["ProjectNumberRequest"]] = relationship(
        back_populates="requester",
        foreign_keys="ProjectNumberRequest.requested_by_id",
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code: Mapped[str] = mapped_column(String(4), unique=True, index=True)
    project_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    special_numbering: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    creator: Mapped[User] = relationship(back_populates="projects")
    file_codes: Mapped[list["FileCode"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    batch_items: Mapped[list["ProjectBatchItem"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    name_review_requests: Mapped[list["NameReviewRequest"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class FileCode(Base):
    __tablename__ = "file_codes"
    __table_args__ = (
        UniqueConstraint("project_id", "standard_name", name="uq_project_standard_name"),
        Index("ix_file_codes_project_enabled", "project_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    original_name: Mapped[str] = mapped_column(Text)
    standard_name: Mapped[str] = mapped_column(Text)
    segment_a: Mapped[str] = mapped_column(String(8))
    segment_b: Mapped[str] = mapped_column(String(8))
    segment_c: Mapped[str] = mapped_column(String(8))
    segment_d: Mapped[str] = mapped_column(String(8))
    segment_e: Mapped[str] = mapped_column(String(8))
    segment_f: Mapped[str] = mapped_column(String(16))
    segment_g: Mapped[str] = mapped_column(String(8), default="")
    segment_h: Mapped[str] = mapped_column(String(8))
    final_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="file_codes")
    claims: Mapped[list["CodeClaim"]] = relationship(
        back_populates="file_code",
        cascade="all, delete-orphan",
    )


class CodeClaim(Base):
    __tablename__ = "code_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_code_id: Mapped[int] = mapped_column(
        ForeignKey("file_codes.id"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    claimant_name: Mapped[str] = mapped_column(String(128))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    file_code: Mapped[FileCode] = relationship(back_populates="claims")
    user: Mapped[User] = relationship(back_populates="claims")


class ProjectBatchItem(Base):
    __tablename__ = "project_batch_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    original_name: Mapped[str] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_codes.id"),
        nullable=True,
    )
    preview_data: Mapped[dict[str, str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    preview_final_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    project: Mapped[Project] = relationship(back_populates="batch_items")
    file_code: Mapped[FileCode | None] = relationship()


class CodeReservation(Base):
    __tablename__ = "code_reservations"

    final_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class NameReviewRequest(Base):
    __tablename__ = "name_review_requests"
    __table_args__ = (Index("ix_name_reviews_project_status", "project_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_name: Mapped[str] = mapped_column(Text)
    proposed_standard_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue_summary: Mapped[str] = mapped_column(Text)
    similar_names: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        default=list,
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    reviewed_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_codes.id"),
        nullable=True,
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    project: Mapped[Project] = relationship(back_populates="name_review_requests")
    requester: Mapped[User] = relationship(
        back_populates="name_review_requests",
        foreign_keys=[requested_by_id],
    )
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    file_code: Mapped[FileCode | None] = relationship()


class ProjectNumberRequest(Base):
    __tablename__ = "project_number_requests"
    __table_args__ = (Index("ix_project_number_requests_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code: Mapped[str] = mapped_column(String(4), index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    processed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    requester: Mapped[User] = relationship(
        back_populates="project_number_requests",
        foreign_keys=[requested_by_id],
    )
    processor: Mapped[User | None] = relationship(foreign_keys=[processed_by_id])


class ComponentProject(Base):
    __tablename__ = "component_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code: Mapped[str] = mapped_column(String(4), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    nodes: Mapped[list["ComponentNode"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ComponentNode(Base):
    __tablename__ = "component_nodes"
    __table_args__ = (
        UniqueConstraint("component_project_id", "code", name="uq_component_nodes_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    component_project_id: Mapped[int] = mapped_column(
        ForeignKey("component_projects.id"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("component_nodes.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(256))
    code: Mapped[str] = mapped_column(String(128))
    stage: Mapped[str] = mapped_column(String(1))
    sequence: Mapped[int] = mapped_column()
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[ComponentProject] = relationship(back_populates="nodes")
    parent: Mapped["ComponentNode | None"] = relationship(remote_side="ComponentNode.id")
    claims: Mapped[list["ComponentClaim"]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


class ComponentClaim(Base):
    __tablename__ = "component_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    component_node_id: Mapped[int] = mapped_column(
        ForeignKey("component_nodes.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    claimant_name: Mapped[str] = mapped_column(String(128))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    node: Mapped[ComponentNode] = relationship(back_populates="claims")


class AuthState(Base):
    __tablename__ = "auth_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(16))
    return_path: Mapped[str] = mapped_column(String(512), default="/")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
