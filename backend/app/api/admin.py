import re
from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    CodeClaim,
    CodeReservation,
    FileCode,
    NameReviewRequest,
    Project,
    ProjectBatchItem,
    ProjectNumberRequest,
    User,
    utcnow,
)
from ..schemas import (
    ApproveNameReviewIn,
    BatchDeleteIn,
    BatchItemOut,
    CodeClaimOut,
    ManualCodeIn,
    NameReviewOut,
    ProjectInitOut,
    ProjectNumberRequestOut,
    ProjectOut,
    RejectNameReviewIn,
    RetryCodeIn,
    SpecialNumberingIn,
)
from ..security import CurrentSession, require_admin, require_csrf
from ..services.abbreviations import get_abbreviation_registry
from ..services.ai_names import NameCorrectionService, normalize_file_name
from ..services.codes import CodeConflictError, CodeService
from ..services.document_rules import standardize_document_terms
from ..services.name_validation import (
    normalized_standard_name,
    validate_user_file_name,
)
from ..services.notifications import notify_review_approved
from ..services.numbering import GeneratedNumber, NumberingService
from ..services.uploads import UploadError, parse_file_names

router = APIRouter(prefix="/api/admin", tags=["管理员"])


def _format_claimed_at(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


def _project_number_request_out(
    request: ProjectNumberRequest,
) -> ProjectNumberRequestOut:
    return ProjectNumberRequestOut(
        id=request.id,
        project_code=request.project_code,
        requested_by_id=request.requested_by_id,
        requester_name=request.requester.name,
        requester_user_id=request.requester.wecom_user_id,
        status=request.status,
        created_at=request.created_at,
        processed_at=request.processed_at,
    )


@router.get(
    "/project-number-requests",
    response_model=list[ProjectNumberRequestOut],
)
def list_project_number_requests(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ProjectNumberRequestOut]:
    requests = db.scalars(
        select(ProjectNumberRequest)
        .where(ProjectNumberRequest.status == "pending")
        .order_by(ProjectNumberRequest.created_at)
    )
    return [_project_number_request_out(request) for request in requests]


@router.post(
    "/project-number-requests/{request_id}/process",
    response_model=ProjectNumberRequestOut,
)
def process_project_number_request(
    request_id: int,
    admin: User = Depends(require_admin),
    _: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ProjectNumberRequestOut:
    request = db.scalar(
        select(ProjectNumberRequest)
        .where(ProjectNumberRequest.id == request_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not request:
        raise HTTPException(status_code=404, detail="新项目编号申请不存在")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="该申请已处理")
    request.status = "processed"
    request.processed_by_id = admin.id
    request.processed_at = utcnow()
    db.commit()
    db.refresh(request)
    return _project_number_request_out(request)


@router.get("/name-reviews", response_model=list[NameReviewOut])
def list_name_reviews(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[NameReviewRequest]:
    return list(
        db.scalars(
            select(NameReviewRequest)
            .where(NameReviewRequest.status == "pending")
            .order_by(NameReviewRequest.created_at)
        )
    )


@router.post(
    "/name-reviews/{review_id}/approve",
    response_model=NameReviewOut,
)
async def approve_name_review(
    review_id: int,
    payload: ApproveNameReviewIn,
    admin: User = Depends(require_admin),
    _: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> NameReviewRequest:
    review = db.scalar(
        select(NameReviewRequest)
        .where(NameReviewRequest.id == review_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not review:
        raise HTTPException(status_code=404, detail="审核申请不存在")
    if review.status != "pending":
        raise HTTPException(status_code=409, detail="该申请已处理")
    project = db.scalar(
        select(Project)
        .where(Project.id == review.project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not project or project.status != "active":
        raise HTTPException(status_code=409, detail="项目不存在或尚未启用")

    service = CodeService(
        db,
        NumberingService(get_abbreviation_registry()),
        NameCorrectionService(),
    )
    try:
        approved_name = validate_user_file_name(payload.file_name)
        normalized_approved = normalized_standard_name(approved_name)
        existing = next(
            (
                code
                for code in db.scalars(
                    select(FileCode).where(
                        FileCode.project_id == project.id,
                        FileCode.enabled.is_(True),
                    )
                )
                if normalized_standard_name(code.standard_name) == normalized_approved
            ),
            None,
        )
        if existing:
            record = existing
        elif project.special_numbering:
            if not payload.final_code:
                raise HTTPException(
                    status_code=400,
                    detail="特殊编号项目必须由管理员填写完整编号",
                )
            final_code = payload.final_code.strip().upper()
            if not re.fullmatch(r"[A-Z0-9._/-]+", final_code):
                raise HTTPException(
                    status_code=400,
                    detail="人工编号只能包含字母、数字、点、横线、下划线或斜杠",
                )
            final_code_existing = db.scalar(
                select(FileCode).where(FileCode.final_code == final_code)
            )
            if final_code_existing:
                raise CodeConflictError(
                    f"编号 {final_code} 已被文件“{final_code_existing.standard_name}”占用"
                )
            service.reserve_code(project.id, final_code)
            record = FileCode(
                project_id=project.id,
                original_name=approved_name,
                standard_name=approved_name,
                segment_a="",
                segment_b=project.project_code,
                segment_c="",
                segment_d="",
                segment_e="",
                segment_f="",
                segment_g="",
                segment_h="",
                final_code=final_code,
                source="user_review_manual",
                enabled=True,
                created_by_id=admin.id,
            )
            db.add(record)
            db.flush()
        else:
            generated = await service.preview_number(approved_name, project)
            record, _ = service.persist_generated(
                project,
                generated,
                admin,
                source="user_review",
                enabled=True,
            )

        review.status = "approved"
        review.reviewed_name = record.standard_name
        review.file_code_id = record.id
        review.reviewed_by_id = admin.id
        review.reviewed_at = utcnow()
        requester = review.requester
        db.commit()
        db.refresh(review)
        await notify_review_approved(
            recipient_user_id=requester.wecom_user_id,
            recipient_name=requester.name,
            project_code=project.project_code,
            project_name=project.project_name,
            reviewed_name=record.standard_name,
            final_code=record.final_code,
        )
        return review
    except HTTPException:
        db.rollback()
        raise
    except CodeConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="编号已被其他操作占用，请刷新后重试",
        ) from exc


@router.post(
    "/name-reviews/{review_id}/reject",
    response_model=NameReviewOut,
)
def reject_name_review(
    review_id: int,
    payload: RejectNameReviewIn,
    admin: User = Depends(require_admin),
    _: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> NameReviewRequest:
    review = db.scalar(
        select(NameReviewRequest)
        .where(NameReviewRequest.id == review_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not review:
        raise HTTPException(status_code=404, detail="审核申请不存在")
    if review.status != "pending":
        raise HTTPException(status_code=409, detail="该申请已处理")
    review.status = "rejected"
    review.issue_summary = payload.reason.strip()
    review.reviewed_by_id = admin.id
    review.reviewed_at = utcnow()
    db.commit()
    db.refresh(review)
    return review


def _lock_project(db: Session, project_id: int) -> Project | None:
    return db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _project_detail(db: Session, project: Project) -> ProjectInitOut:
    claims_by_code: dict[int, list[CodeClaimOut]] = {}
    claims = db.scalars(
        select(CodeClaim)
        .join(FileCode, CodeClaim.file_code_id == FileCode.id)
        .where(FileCode.project_id == project.id)
        .order_by(CodeClaim.claimed_at, CodeClaim.id)
    )
    for claim in claims:
        claims_by_code.setdefault(claim.file_code_id, []).append(CodeClaimOut.model_validate(claim))

    batch_items = list(
        db.scalars(
            select(ProjectBatchItem)
            .where(ProjectBatchItem.project_id == project.id)
            .order_by(ProjectBatchItem.id)
        )
    )
    items = [
        BatchItemOut(
            id=item.id,
            file_code_id=item.file_code_id,
            original_name=item.original_name,
            success=item.success,
            standard_name=(
                item.file_code.standard_name
                if item.file_code
                else (item.preview_data or {}).get("standard_name")
            ),
            final_code=(
                item.file_code.final_code
                if item.file_code
                else (item.preview_data or {}).get("final_code")
            ),
            error=item.error,
            claims=(
                claims_by_code.get(item.file_code_id, []) if item.file_code_id is not None else []
            ),
        )
        for item in batch_items
    ]

    linked_code_ids = {item.file_code_id for item in batch_items if item.file_code_id is not None}
    all_codes = db.scalars(
        select(FileCode).where(FileCode.project_id == project.id).order_by(FileCode.created_at)
    )
    items.extend(
        BatchItemOut(
            file_code_id=code.id,
            original_name=code.original_name,
            success=True,
            standard_name=code.standard_name,
            final_code=code.final_code,
            claims=claims_by_code.get(code.id, []),
        )
        for code in all_codes
        if code.id not in linked_code_ids
    )
    success_count = sum(item.success for item in items)
    return ProjectInitOut(
        project=project,
        items=items,
        success_count=success_count,
        failure_count=len(items) - success_count,
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.post(
    "/projects/{project_id}/special-numbering",
    response_model=ProjectOut,
)
def set_project_special_numbering(
    project_id: int,
    payload: SpecialNumberingIn,
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Project:
    project = _lock_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status == "initializing":
        raise HTTPException(status_code=409, detail="项目正在批量生成，暂不能修改")
    project.special_numbering = payload.special_numbering
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectInitOut)
def get_project_detail(
    project_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProjectInitOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return _project_detail(db, project)


@router.get("/projects/{project_id}/export")
def export_project_codes(
    project_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status != "active":
        raise HTTPException(status_code=409, detail="项目尚未启用，不能导出")

    unresolved_item = db.scalar(
        select(ProjectBatchItem.id)
        .where(
            ProjectBatchItem.project_id == project_id,
            ProjectBatchItem.file_code_id.is_(None),
        )
        .limit(1)
    )
    if unresolved_item is not None:
        raise HTTPException(
            status_code=409,
            detail="仍有待确认、失败或已重复文件，全部处理后才能导出",
        )

    file_codes = list(
        db.scalars(
            select(FileCode)
            .where(
                FileCode.project_id == project_id,
                FileCode.enabled.is_(True),
            )
            .order_by(FileCode.standard_name, FileCode.id)
        )
    )
    if not file_codes:
        raise HTTPException(status_code=409, detail="项目编码库为空，不能导出")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文件编码"
    sheet.append(["文件名称", "文件编号"])
    for file_code in file_codes:
        sheet.append([file_code.standard_name, file_code.final_code])

    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    sheet.column_dimensions["A"].width = 64
    sheet.column_dimensions["B"].width = 40
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    claim_sheet = workbook.create_sheet("领取记录")
    claim_sheet.append(["文件名称", "文件编号", "领取人", "领取时间"])
    claim_rows = db.execute(
        select(CodeClaim, FileCode)
        .join(FileCode, CodeClaim.file_code_id == FileCode.id)
        .where(FileCode.project_id == project_id)
        .order_by(CodeClaim.claimed_at, CodeClaim.id)
    )
    for claim, file_code in claim_rows:
        claim_sheet.append(
            [
                file_code.standard_name,
                file_code.final_code,
                claim.claimant_name,
                _format_claimed_at(claim.claimed_at),
            ]
        )
    for cell in claim_sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    claim_sheet.column_dimensions["A"].width = 64
    claim_sheet.column_dimensions["B"].width = 40
    claim_sheet.column_dimensions["C"].width = 22
    claim_sheet.column_dimensions["D"].width = 24
    claim_sheet.freeze_panes = "A2"
    claim_sheet.auto_filter.ref = claim_sheet.dimensions

    content = BytesIO()
    workbook.save(content)
    workbook.close()
    content.seek(0)

    filename = f"{project.project_code}-{project.project_name}-文件编码.xlsx"
    encoded_filename = quote(filename)
    return StreamingResponse(
        content,
        media_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        headers={"Content-Disposition": (f"attachment; filename*=UTF-8''{encoded_filename}")},
    )


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> None:
    project = _lock_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    file_code_ids = select(FileCode.id).where(FileCode.project_id == project_id)
    db.execute(delete(CodeClaim).where(CodeClaim.file_code_id.in_(file_code_ids)))
    db.execute(delete(NameReviewRequest).where(NameReviewRequest.project_id == project_id))
    db.execute(delete(ProjectBatchItem).where(ProjectBatchItem.project_id == project_id))
    db.execute(delete(FileCode).where(FileCode.project_id == project_id))
    db.execute(delete(CodeReservation).where(CodeReservation.project_id == project_id))
    db.delete(project)
    db.commit()


@router.post("/projects/init", response_model=ProjectInitOut)
async def initialize_project(
    project_name: str = Form(min_length=1, max_length=128),
    project_code: str = Form(pattern=r"^\d{4}$"),
    special_numbering: bool = Form(default=False),
    file: UploadFile = File(),
    admin: User = Depends(require_admin),
    _: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ProjectInitOut:
    existing = db.scalar(select(Project).where(Project.project_code == project_code))
    if existing:
        raise HTTPException(status_code=409, detail="该项目号已存在")
    try:
        file_names = parse_file_names(file.filename or "", await file.read())
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    project = Project(
        project_code=project_code,
        project_name=project_name,
        status="initializing",
        special_numbering=special_numbering,
        created_by_id=admin.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    project_id = project.id

    service = CodeService(
        db,
        NumberingService(get_abbreviation_registry()),
        NameCorrectionService(),
    )
    try:
        items = await service.generate_batch(project, file_names)
        project = _lock_project(db, project_id)
        if not project:
            db.rollback()
            raise HTTPException(status_code=409, detail="项目已被管理员删除")
        project.status = "draft"
        db.commit()
        db.refresh(project)
    except BaseException:
        db.rollback()
        failed_project = db.get(Project, project_id)
        if failed_project and failed_project.status == "initializing":
            failed_project.status = "failed"
            try:
                db.commit()
            except Exception:
                db.rollback()
        raise
    success_count = sum(item.success for item in items)
    return ProjectInitOut(
        project=project,
        items=items,
        success_count=success_count,
        failure_count=len(items) - success_count,
    )


@router.post("/projects/{project_id}/codes", response_model=BatchItemOut)
async def add_project_code(
    project_id: int,
    payload: RetryCodeIn,
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> BatchItemOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status not in {"draft", "active"}:
        detail = (
            "项目正在批量生成，请稍后再试"
            if project.status == "initializing"
            else "项目初始化失败，请删除项目后重新初始化"
        )
        raise HTTPException(status_code=409, detail=detail)

    service = CodeService(
        db,
        NumberingService(get_abbreviation_registry()),
        NameCorrectionService(),
    )
    try:
        return (await service.generate_batch(project, [payload.file_name]))[0]
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="编号已被其他操作占用，请刷新后重试",
        ) from exc


@router.post("/projects/{project_id}/codes/import", response_model=ProjectInitOut)
async def import_project_codes(
    project_id: int,
    file: UploadFile = File(),
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ProjectInitOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status not in {"draft", "active"}:
        detail = (
            "项目正在批量生成，请稍后再试"
            if project.status == "initializing"
            else "项目初始化失败，请删除项目后重新初始化"
        )
        raise HTTPException(status_code=409, detail=detail)
    try:
        file_names = parse_file_names(file.filename or "", await file.read())
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = CodeService(
        db,
        NumberingService(get_abbreviation_registry()),
        NameCorrectionService(),
    )
    await service.generate_batch(project, file_names)
    db.refresh(project)
    return _project_detail(db, project)


@router.post(
    "/projects/{project_id}/codes/manual",
    response_model=BatchItemOut,
)
def add_manual_project_code(
    project_id: int,
    payload: ManualCodeIn,
    admin: User = Depends(require_admin),
    _: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> BatchItemOut:
    project = _lock_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status not in {"draft", "active"}:
        detail = (
            "项目正在批量生成，请稍后再试"
            if project.status == "initializing"
            else "项目初始化失败，请删除项目后重新初始化"
        )
        raise HTTPException(status_code=409, detail=detail)

    numbering = NumberingService(get_abbreviation_registry())
    service = CodeService(db, numbering, NameCorrectionService())
    try:
        generated = numbering.parse_manual_code(
            payload.file_name,
            payload.final_code,
            project.project_code,
        )
        existing = db.scalar(
            select(FileCode).where(
                FileCode.project_id == project.id,
                FileCode.standard_name == generated.standard_name,
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"该文件已存在编码 {existing.final_code}",
            )
        pending_items = db.scalars(
            select(ProjectBatchItem).where(
                ProjectBatchItem.project_id == project.id,
                ProjectBatchItem.success.is_(True),
                ProjectBatchItem.file_code_id.is_(None),
            )
        )
        if any(
            (item.preview_data or {}).get("standard_name") == generated.standard_name
            for item in pending_items
        ):
            raise HTTPException(
                status_code=409,
                detail="该文件已在待确认列表中",
            )

        batch_item = service.stage_generated(
            project,
            payload.file_name,
            generated,
        )
        db.commit()
        db.refresh(batch_item)
        return BatchItemOut(
            id=batch_item.id,
            original_name=batch_item.original_name,
            success=True,
            standard_name=generated.standard_name,
            final_code=generated.final_code,
        )
    except HTTPException:
        db.rollback()
        raise
    except CodeConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="编号已被其他操作占用，请刷新后重试",
        ) from exc


@router.delete("/projects/{project_id}/codes/{file_code_id}", status_code=204)
def delete_project_code(
    project_id: int,
    file_code_id: int,
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> None:
    project = _lock_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    file_code = db.scalar(
        select(FileCode).where(
            FileCode.id == file_code_id,
            FileCode.project_id == project_id,
        )
    )
    if not file_code:
        raise HTTPException(status_code=404, detail="文件及编码不存在")

    db.execute(delete(CodeClaim).where(CodeClaim.file_code_id == file_code_id))
    db.execute(
        update(NameReviewRequest)
        .where(NameReviewRequest.file_code_id == file_code_id)
        .values(
            file_code_id=None,
            status="rejected",
            issue_summary="审核生成的编号已由管理员删除",
        )
    )
    db.execute(delete(ProjectBatchItem).where(ProjectBatchItem.file_code_id == file_code_id))
    db.execute(delete(CodeReservation).where(CodeReservation.final_code == file_code.final_code))
    db.delete(file_code)
    db.commit()


@router.post("/projects/{project_id}/files/batch-delete", status_code=204)
def batch_delete_project_files(
    project_id: int,
    payload: BatchDeleteIn,
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> None:
    project = _lock_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status == "initializing":
        raise HTTPException(status_code=409, detail="项目正在批量生成，暂不能修改")

    file_code_ids = set(payload.file_code_ids)
    batch_item_ids = set(payload.batch_item_ids)
    if not file_code_ids and not batch_item_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个文件")
    if any(item_id <= 0 for item_id in file_code_ids | batch_item_ids):
        raise HTTPException(status_code=400, detail="所选文件标识无效")

    file_codes = list(
        db.scalars(
            select(FileCode)
            .where(
                FileCode.project_id == project_id,
                FileCode.id.in_(file_code_ids),
            )
            .with_for_update()
        )
    )
    if len(file_codes) != len(file_code_ids):
        raise HTTPException(status_code=404, detail="部分已选文件或编码不存在")

    batch_items = list(
        db.scalars(
            select(ProjectBatchItem)
            .where(
                ProjectBatchItem.project_id == project_id,
                ProjectBatchItem.id.in_(batch_item_ids),
            )
            .with_for_update()
        )
    )
    if len(batch_items) != len(batch_item_ids):
        raise HTTPException(status_code=404, detail="部分已选批次文件不存在")
    if any(item.file_code_id is not None for item in batch_items):
        raise HTTPException(status_code=409, detail="已入库文件必须按编码选择删除")

    selected_final_codes = {file_code.final_code for file_code in file_codes}
    selected_final_codes.update(
        item.preview_final_code for item in batch_items if item.preview_final_code
    )

    if file_code_ids:
        db.execute(delete(CodeClaim).where(CodeClaim.file_code_id.in_(file_code_ids)))
        db.execute(
            update(NameReviewRequest)
            .where(NameReviewRequest.file_code_id.in_(file_code_ids))
            .values(
                file_code_id=None,
                status="rejected",
                issue_summary="审核生成的编号已由管理员删除",
            )
        )
        db.execute(delete(ProjectBatchItem).where(ProjectBatchItem.file_code_id.in_(file_code_ids)))
    if selected_final_codes:
        db.execute(
            delete(CodeReservation).where(CodeReservation.final_code.in_(selected_final_codes))
        )
    if batch_item_ids:
        db.execute(delete(ProjectBatchItem).where(ProjectBatchItem.id.in_(batch_item_ids)))
    if file_code_ids:
        db.execute(delete(FileCode).where(FileCode.id.in_(file_code_ids)))
    db.commit()


@router.delete(
    "/projects/{project_id}/batch-items/{batch_item_id}",
    status_code=204,
)
def delete_staged_batch_item(
    project_id: int,
    batch_item_id: int,
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> None:
    project = _lock_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status == "initializing":
        raise HTTPException(status_code=409, detail="项目正在批量生成，暂不能修改")
    batch_item = db.scalar(
        select(ProjectBatchItem)
        .where(
            ProjectBatchItem.id == batch_item_id,
            ProjectBatchItem.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not batch_item:
        raise HTTPException(status_code=404, detail="待确认文件不存在")
    if batch_item.file_code_id is not None:
        raise HTTPException(status_code=409, detail="该编码已入库，请按编码删除")

    if batch_item.preview_final_code:
        db.execute(
            delete(CodeReservation).where(
                CodeReservation.final_code == batch_item.preview_final_code
            )
        )
    db.delete(batch_item)
    db.commit()


@router.post("/projects/{project_id}/confirm", response_model=ProjectOut)
def confirm_project(
    project_id: int,
    admin: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Project:
    project = _lock_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status not in {"draft", "active"}:
        raise HTTPException(status_code=409, detail="项目正在批量生成，请稍后确认")

    pending_items = list(
        db.scalars(
            select(ProjectBatchItem)
            .where(
                ProjectBatchItem.project_id == project.id,
                ProjectBatchItem.success.is_(True),
                ProjectBatchItem.file_code_id.is_(None),
            )
            .order_by(ProjectBatchItem.id)
        )
    )
    if not pending_items:
        if project.status == "active":
            return project
        raise HTTPException(status_code=409, detail="没有可确认的成功编码")

    service = CodeService(
        db,
        NumberingService(get_abbreviation_registry()),
        NameCorrectionService(),
    )
    try:
        for item in pending_items:
            service.persist_preview(project, item, admin)
        db.execute(update(FileCode).where(FileCode.project_id == project.id).values(enabled=True))
        project.status = "active"
        db.commit()
        db.refresh(project)
        return project
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"确认入库失败：{exc}",
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="确认入库失败：编码已被其他操作占用，请刷新后重试",
        ) from exc


@router.post(
    "/projects/{project_id}/batch-items/{batch_item_id}/retry",
    response_model=BatchItemOut,
)
async def retry_failed_code(
    project_id: int,
    batch_item_id: int,
    payload: RetryCodeIn,
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> BatchItemOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status not in {"draft", "active"}:
        raise HTTPException(status_code=409, detail="当前项目状态不能修改批量结果")
    batch_item = db.scalar(
        select(ProjectBatchItem).where(
            ProjectBatchItem.id == batch_item_id,
            ProjectBatchItem.project_id == project_id,
        )
    )
    if not batch_item:
        raise HTTPException(status_code=404, detail="批量失败项不存在")
    if batch_item.success:
        raise HTTPException(status_code=409, detail="该文件已经生成成功")

    file_name = payload.file_name.strip()
    service = CodeService(
        db,
        NumberingService(get_abbreviation_registry()),
        NameCorrectionService(),
    )
    try:
        generated = await service.preview_number(
            file_name,
            project,
            exclude_batch_item_id=batch_item.id,
        )
        project = _lock_project(db, project_id)
        if not project:
            db.rollback()
            raise HTTPException(status_code=404, detail="项目不存在")
        if project.status not in {"draft", "active"}:
            db.rollback()
            raise HTTPException(status_code=409, detail="项目状态已变化，请刷新后重试")
        batch_item = db.scalar(
            select(ProjectBatchItem)
            .where(
                ProjectBatchItem.id == batch_item_id,
                ProjectBatchItem.project_id == project_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not batch_item:
            db.rollback()
            raise HTTPException(status_code=404, detail="批量失败项不存在")
        if batch_item.success:
            db.rollback()
            raise HTTPException(status_code=409, detail="该文件已经生成成功")

        service.reserve_code(project.id, generated.final_code)
        batch_item.success = True
        batch_item.error = None
        batch_item.file_code_id = None
        batch_item.preview_data = asdict(generated)
        batch_item.preview_final_code = generated.final_code
        db.commit()
        db.refresh(batch_item)
        return BatchItemOut(
            id=batch_item.id,
            original_name=batch_item.original_name,
            success=True,
            standard_name=generated.standard_name,
            final_code=generated.final_code,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        batch_item = db.get(ProjectBatchItem, batch_item_id)
        if not batch_item:
            raise HTTPException(status_code=404, detail="批量失败项不存在") from exc
        if batch_item.success:
            raise HTTPException(
                status_code=409,
                detail="该文件已由其他操作生成，请刷新项目",
            ) from exc
        batch_item.success = False
        batch_item.error = str(exc)
        batch_item.file_code_id = None
        batch_item.preview_data = None
        batch_item.preview_final_code = None
        db.commit()
        return BatchItemOut(
            id=batch_item.id,
            original_name=batch_item.original_name,
            success=False,
            error=str(exc),
        )


@router.post(
    "/projects/{project_id}/batch-items/{batch_item_id}/manual",
    response_model=BatchItemOut,
)
def manually_number_batch_item(
    project_id: int,
    batch_item_id: int,
    payload: ManualCodeIn,
    _: User = Depends(require_admin),
    __: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> BatchItemOut:
    project = _lock_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status not in {"draft", "active"}:
        raise HTTPException(status_code=409, detail="当前项目状态不能修改批量结果")

    batch_item = db.scalar(
        select(ProjectBatchItem)
        .where(
            ProjectBatchItem.id == batch_item_id,
            ProjectBatchItem.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not batch_item:
        raise HTTPException(status_code=404, detail="批量项目不存在")
    if batch_item.file_code_id is not None:
        raise HTTPException(status_code=409, detail="该编码已入库，不能修改")

    numbering = NumberingService(get_abbreviation_registry())
    service = CodeService(db, numbering, NameCorrectionService())
    try:
        standard_name = standardize_document_terms(normalize_file_name(payload.file_name))
        if not standard_name:
            raise ValueError("文件名称不能为空")
        final_code = payload.final_code.strip()
        if not final_code:
            raise ValueError("文件编号不能为空")

        preview_data = dict(batch_item.preview_data or {})
        generated = GeneratedNumber(
            original_name=batch_item.original_name,
            standard_name=standard_name,
            segment_a=str(preview_data.get("segment_a", "")),
            segment_b=str(preview_data.get("segment_b", project.project_code)),
            segment_c=str(preview_data.get("segment_c", "")),
            segment_d=str(preview_data.get("segment_d", "")),
            segment_e=str(preview_data.get("segment_e", "")),
            segment_f=str(preview_data.get("segment_f", "")),
            segment_g=str(preview_data.get("segment_g", "")),
            segment_h=str(preview_data.get("segment_h", "")),
            final_code=final_code,
        )
        existing = db.scalar(
            select(FileCode).where(
                FileCode.project_id == project.id,
                FileCode.standard_name == generated.standard_name,
            )
        )
        if existing:
            raise CodeConflictError(
                f"文件“{generated.standard_name}”已存在编码 {existing.final_code}"
            )

        pending_items = db.scalars(
            select(ProjectBatchItem).where(
                ProjectBatchItem.project_id == project.id,
                ProjectBatchItem.success.is_(True),
                ProjectBatchItem.file_code_id.is_(None),
                ProjectBatchItem.id != batch_item.id,
            )
        )
        if any(
            (item.preview_data or {}).get("standard_name") == generated.standard_name
            for item in pending_items
        ):
            raise CodeConflictError("该文件已在待确认列表中")

        existing_code = db.scalar(
            select(FileCode).where(FileCode.final_code == generated.final_code)
        )
        if existing_code:
            raise CodeConflictError(
                f"编码 {generated.final_code} 已被文件“{existing_code.standard_name}”占用"
            )

        previous_final_code = batch_item.preview_final_code
        reservation = db.get(CodeReservation, generated.final_code)
        if reservation and generated.final_code != previous_final_code:
            raise CodeConflictError(f"编码 {generated.final_code} 已被全局占用")

        if previous_final_code != generated.final_code:
            if previous_final_code:
                db.execute(
                    delete(CodeReservation).where(
                        CodeReservation.final_code == previous_final_code,
                        CodeReservation.project_id == project.id,
                    )
                )
                db.flush()
            service.reserve_code(project.id, generated.final_code)
        elif reservation is None:
            service.reserve_code(project.id, generated.final_code)

        batch_item.success = True
        batch_item.error = None
        batch_item.file_code_id = None
        batch_item.preview_data = asdict(generated)
        batch_item.preview_final_code = generated.final_code
        db.commit()
        db.refresh(batch_item)
        return BatchItemOut(
            id=batch_item.id,
            original_name=batch_item.original_name,
            success=True,
            standard_name=generated.standard_name,
            final_code=generated.final_code,
        )
    except CodeConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="编号已被其他操作占用，请重新填写",
        ) from exc
