from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CodeClaim, FileCode, Project, User
from ..schemas import ClaimOut, FileCodeOut, GenerateCodeIn, ProjectOut
from ..security import CurrentSession, require_csrf, require_user
from ..services.abbreviations import get_abbreviation_registry
from ..services.ai_names import NameCorrectionService, normalize_file_name
from ..services.codes import CodeService
from ..services.numbering import NumberingService

router = APIRouter(prefix="/api", tags=["编码"])


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
    normalized = normalize_file_name(name)
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
    claim = CodeClaim(file_code_id=file_code.id, user_id=user.id)
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return ClaimOut(file_code=file_code, claimed_at=claim.claimed_at)


@router.post("/codes/generate", response_model=FileCodeOut)
async def generate_missing_code(
    payload: GenerateCodeIn,
    user: User = Depends(require_user),
    _: CurrentSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> FileCode:
    project = db.get(Project, payload.project_id)
    if not project or project.status != "active":
        raise HTTPException(status_code=404, detail="项目不存在或尚未启用")
    service = CodeService(
        db,
        NumberingService(get_abbreviation_registry()),
        NameCorrectionService(),
    )
    try:
        generated = await service.preview_number(
            payload.file_name,
            project,
            check_existing=False,
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
        return record
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="编号已被其他操作占用，请刷新后重试",
        ) from exc
