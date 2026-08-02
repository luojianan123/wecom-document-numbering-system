from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    CodeClaim,
    CodeReservation,
    FileCode,
    NameReviewRequest,
    Project,
    User,
)
from ..schemas import (
    ClaimOut,
    FileCodeOut,
    GenerateCodeIn,
    GenerateCodeOut,
    NameReviewOut,
    ProjectOut,
)
from ..security import CurrentSession, require_csrf, require_user
from ..services.abbreviations import get_abbreviation_registry
from ..services.ai_names import NameCorrectionService
from ..services.codes import CodeService
from ..services.name_validation import (
    find_similar_names,
    is_obviously_unrelated_name,
    normalized_standard_name,
    validate_user_file_name,
)
from ..services.notifications import notify_admin_review_requested
from ..services.numbering import NumberingService

router = APIRouter(prefix="/api", tags=["编码"])


def _get_or_create_pending_review(
    db: Session,
    *,
    project: Project,
    user: User,
    original_name: str,
    proposed_standard_name: str,
    issue_summary: str,
    similar_names: list[dict[str, object]],
) -> tuple[NameReviewRequest, bool]:
    pending = db.scalar(
        select(NameReviewRequest).where(
            NameReviewRequest.project_id == project.id,
            NameReviewRequest.requested_by_id == user.id,
            NameReviewRequest.status == "pending",
            NameReviewRequest.proposed_standard_name == proposed_standard_name,
        )
    )
    if pending:
        return pending, False
    pending = NameReviewRequest(
        project_id=project.id,
        requested_by_id=user.id,
        original_name=original_name,
        proposed_standard_name=proposed_standard_name,
        issue_summary=issue_summary,
        similar_names=similar_names,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending, True


async def _notify_new_review(
    review: NameReviewRequest,
    project: Project,
    user: User,
    created: bool,
) -> None:
    if not created:
        return
    await notify_admin_review_requested(
        review_id=review.id,
        project_code=project.project_code,
        project_name=project.project_name,
        requester_name=user.name,
        requester_user_id=user.wecom_user_id,
        requested_name=review.proposed_standard_name or review.original_name,
        issue_summary=review.issue_summary,
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_active_projects(
    _: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[Project]:
    return list(
        db.scalars(
            select(Project)
            .where(Project.status == "active")
            .order_by(Project.project_code)
        )
    )


@router.get(
    "/projects/{project_id}/codes",
    response_model=list[FileCodeOut],
)
def list_project_codes(
    project_id: int,
    _: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[FileCode]:
    project = db.get(Project, project_id)
    if not project or project.status != "active":
        raise HTTPException(status_code=404, detail="项目不存在或尚未启用")
    return list(
        db.scalars(
            select(FileCode)
            .where(
                FileCode.project_id == project_id,
                FileCode.enabled.is_(True),
            )
            .order_by(FileCode.standard_name, FileCode.id)
        )
    )


@router.get("/codes/search", response_model=list[FileCodeOut])
def search_codes(
    project_id: int,
    name: str = Query(min_length=1, max_length=512),
    _: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[FileCode]:
    project = db.get(Project, project_id)
    if not project or project.status != "active":
        raise HTTPException(status_code=404, detail="项目不存在或尚未启用")
    try:
        normalized = validate_user_file_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if is_obviously_unrelated_name(
        normalized,
        get_abbreviation_registry(),
    ):
        return []
    return list(
        db.scalars(
            select(FileCode)
            .where(
                FileCode.project_id == project_id,
                FileCode.enabled.is_(True),
                or_(
                    FileCode.standard_name.contains(normalized),
                    FileCode.original_name.contains(name),
                ),
            )
            .order_by(FileCode.standard_name)
            .limit(50)
        )
    )


@router.post("/codes/{file_code_id}/claim", response_model=ClaimOut)
def claim_code(
    file_code_id: int,
    user: User = Depends(require_user),
    _: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ClaimOut:
    file_code = db.get(FileCode, file_code_id)
    if not file_code or not file_code.enabled:
        raise HTTPException(status_code=404, detail="编码不存在或尚未启用")
    claim = CodeClaim(
        file_code_id=file_code.id,
        user_id=user.id,
        claimant_name=user.name,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return ClaimOut(
        file_code=file_code,
        claimant_name=claim.claimant_name,
        claimed_at=claim.claimed_at,
    )


@router.get("/name-reviews/mine", response_model=list[NameReviewOut])
def list_my_name_reviews(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[NameReviewRequest]:
    return list(
        db.scalars(
            select(NameReviewRequest)
            .where(NameReviewRequest.requested_by_id == user.id)
            .order_by(NameReviewRequest.created_at.desc())
        )
    )


@router.post("/codes/generate", response_model=GenerateCodeOut)
async def generate_missing_code(
    payload: GenerateCodeIn,
    user: User = Depends(require_user),
    _: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> GenerateCodeOut:
    project = db.get(Project, payload.project_id)
    if not project or project.status != "active":
        raise HTTPException(status_code=404, detail="项目不存在或尚未启用")
    name_correction = NameCorrectionService()
    service = CodeService(
        db,
        NumberingService(get_abbreviation_registry()),
        name_correction,
    )
    try:
        submitted_name = validate_user_file_name(payload.file_name)
        correction = await name_correction.correct(
            submitted_name,
            project.project_code,
        )
        candidate_name = correction.standard_name
        existing_codes = list(
            db.scalars(
                select(FileCode).where(
                    FileCode.project_id == project.id,
                    FileCode.enabled.is_(True),
                )
            )
        )
        normalized_candidate = normalized_standard_name(candidate_name)
        existing = next(
            (
                item
                for item in existing_codes
                if normalized_standard_name(item.standard_name)
                == normalized_candidate
            ),
            None,
        )
        if existing:
            return GenerateCodeOut(
                status="existing",
                message="文件名称已存在，已返回现有编号",
                file_code=existing,
            )

        if project.special_numbering:
            pending, created = _get_or_create_pending_review(
                db,
                project=project,
                user=user,
                original_name=payload.file_name.strip(),
                proposed_standard_name=candidate_name,
                issue_summary="该项目有其他编号要求，请等待管理员人工编号",
                similar_names=[],
            )
            await _notify_new_review(pending, project, user, created)
            return GenerateCodeOut(
                status="pending_review",
                message="该项目有其他编号要求，请等待管理员人工编号",
                review=pending,
            )

        if is_obviously_unrelated_name(
            candidate_name,
            get_abbreviation_registry(),
        ):
            pending, created = _get_or_create_pending_review(
                db,
                project=project,
                user=user,
                original_name=payload.file_name.strip(),
                proposed_standard_name=candidate_name,
                issue_summary=(
                    "检测到明显生活化、个人表达或非工程文件内容，"
                    "需要管理员确认"
                ),
                similar_names=[],
            )
            await _notify_new_review(pending, project, user, created)
            return GenerateCodeOut(
                status="pending_review",
                message="文件名称疑似非工程内容，已提交管理员审核",
                review=pending,
            )
        similar_names = find_similar_names(
            candidate_name,
            [item.standard_name for item in existing_codes],
        )
        if similar_names:
            pending, created = _get_or_create_pending_review(
                db,
                project=project,
                user=user,
                original_name=payload.file_name.strip(),
                proposed_standard_name=candidate_name,
                issue_summary="检测到同项目相似文件名称，需要管理员确认",
                similar_names=[
                    {
                        "standard_name": item.standard_name,
                        "score": item.score,
                    }
                    for item in similar_names
                ],
            )
            await _notify_new_review(pending, project, user, created)
            return GenerateCodeOut(
                status="pending_review",
                message="检测到相似文件名称，已提交管理员审核",
                review=pending,
            )

        unavailable_final_codes = set(
            db.scalars(select(FileCode.final_code))
        )
        unavailable_final_codes.update(
            db.scalars(select(CodeReservation.final_code))
        )
        generated = service.numbering.generate(
            submitted_name,
            correction,
            project.project_code,
            unavailable_final_codes=unavailable_final_codes,
        )
        project = db.scalar(
            select(Project)
            .where(Project.id == payload.project_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not project or project.status != "active":
            db.rollback()
            raise HTTPException(status_code=404, detail="项目不存在或尚未启用")
        record, _ = service.persist_generated(
            project,
            generated,
            user,
            source="user_missing",
            enabled=True,
        )
        db.commit()
        db.refresh(record)
        return GenerateCodeOut(
            status="generated",
            message="文件名称校验通过，编号已生成",
            file_code=record,
        )
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        try:
            submitted_name = validate_user_file_name(payload.file_name)
        except ValueError:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        pending, created = _get_or_create_pending_review(
            db,
            project=project,
            user=user,
            original_name=payload.file_name.strip(),
            proposed_standard_name=submitted_name,
            issue_summary=f"自动检测或编号失败：{exc}",
            similar_names=[],
        )
        await _notify_new_review(pending, project, user, created)
        return GenerateCodeOut(
            status="pending_review",
            message="名称自动检测出现问题，已提交管理员审核",
            review=pending,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="编号已被其他操作占用，请刷新后重试",
        ) from exc
