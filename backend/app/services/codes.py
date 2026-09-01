from collections import defaultdict
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CodeReservation, FileCode, Project, ProjectBatchItem, User
from ..schemas import BatchItemOut
from .ai_names import NameCorrectionService
from .name_validation import function_subject_key, normalized_standard_name
from .numbering import GeneratedNumber, NumberingService


class CodeConflictError(ValueError):
    pass


SUBJECT_FUNCTION_CODES = {
    "安全控制器": "QA",
    "发动机控制器": "KZ",
}


class _BatchState:
    """Indexes used only during one batch to avoid repeated full-table scans."""

    def __init__(self, service: "CodeService", project: Project) -> None:
        existing_items = list(
            service.db.scalars(select(FileCode).where(FileCode.project_id == project.id))
        )
        self.existing_codes_by_name = {
            item.standard_name: item.final_code for item in existing_items
        }
        self.staged_names: set[str] = set()
        self.unavailable_codes = set(
            service.db.scalars(select(CodeReservation.final_code))
        )
        self.unavailable_codes.update(
            service.db.scalars(select(FileCode.final_code))
        )
        self.function_codes_by_subject: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for item in existing_items:
            if item.segment_d:
                subject_key = service.function_subject_key(project, item.standard_name)
                if subject_key:
                    self.function_codes_by_subject[subject_key].add(
                        (normalized_standard_name(item.standard_name), item.segment_d)
                    )

        for item in service.db.scalars(
            select(ProjectBatchItem).where(
                ProjectBatchItem.project_id == project.id,
                ProjectBatchItem.success.is_(True),
                ProjectBatchItem.file_code_id.is_(None),
            )
        ):
            if not item.preview_data:
                continue
            standard_name = str(item.preview_data.get("standard_name", ""))
            self.staged_names.add(standard_name)
            segment_d = str(item.preview_data.get("segment_d", ""))
            if segment_d:
                subject_key = service.function_subject_key(project, standard_name)
                if subject_key:
                    self.function_codes_by_subject[subject_key].add(
                        (normalized_standard_name(standard_name), segment_d)
                    )


class CodeService:
    def __init__(
        self,
        db: Session,
        numbering: NumberingService,
        name_correction: NameCorrectionService,
    ):
        self.db = db
        self.numbering = numbering
        self.name_correction = name_correction
        self._batch_state: _BatchState | None = None

    def function_subject_key(self, project: Project, standard_name: str) -> str:
        normalized_name = normalized_standard_name(standard_name)
        registered_subjects = [
            *(('software', name) for name in project.software_names),
            *(('board', name) for name in project.board_names),
            *(('product', name) for name in project.product_names),
        ]
        matches = [
            (subject_type, normalized_standard_name(subject_name), subject_name.strip())
            for subject_type, subject_name in registered_subjects
            if subject_name.strip()
            and normalized_standard_name(subject_name) in normalized_name
        ]
        if matches:
            subject_type, normalized_subject, _ = max(matches, key=lambda item: len(item[1]))
            return f"{subject_type}:{normalized_subject}"
        return function_subject_key(standard_name, self.numbering.abbreviations)

    @staticmethod
    def configured_subject_function_code(project: Project, standard_name: str) -> str | None:
        normalized_name = normalized_standard_name(standard_name)
        matches = [
            (subject_name.strip(), code)
            for subject_name, code in SUBJECT_FUNCTION_CODES.items()
            if normalized_standard_name(subject_name) in normalized_name
            and any(
                normalized_standard_name(subject_name) == normalized_standard_name(registered)
                for registered in project.product_names
            )
        ]
        return max(matches, key=lambda item: len(item[0]))[1] if matches else None

    def required_function_code(
        self,
        project_id: int,
        standard_name: str,
        *,
        exclude_batch_item_id: int | None = None,
    ) -> str | None:
        project = self.db.get(Project, project_id)
        if not project:
            return None
        subject_key = self.function_subject_key(project, standard_name)
        if not subject_key:
            return None
        normalized_name = normalized_standard_name(standard_name)

        if self._batch_state is not None:
            function_codes = {
                code
                for name, code in self._batch_state.function_codes_by_subject.get(
                    subject_key, set()
                )
                if name != normalized_name
            }
            if len(function_codes) > 1:
                codes = "、".join(sorted(function_codes))
                raise CodeConflictError(f"同一软件、板卡或产品存在多个历史功能码：{codes}")
            return next(
                iter(function_codes),
                self.configured_subject_function_code(project, standard_name),
            )

        function_codes = {
            item.segment_d
            for item in self.db.scalars(
                select(FileCode).where(FileCode.project_id == project_id)
            )
            if item.segment_d
            and normalized_standard_name(item.standard_name) != normalized_name
            and self.function_subject_key(project, item.standard_name) == subject_key
        }
        staged_items = self.db.scalars(
            select(ProjectBatchItem).where(
                ProjectBatchItem.project_id == project_id,
                ProjectBatchItem.success.is_(True),
                ProjectBatchItem.file_code_id.is_(None),
            )
        )
        for item in staged_items:
            if item.id == exclude_batch_item_id or not item.preview_data:
                continue
            preview_name = str(item.preview_data.get("standard_name", ""))
            preview_function_code = str(item.preview_data.get("segment_d", ""))
            if (
                preview_function_code
                and normalized_standard_name(preview_name) != normalized_name
                and self.function_subject_key(project, preview_name) == subject_key
            ):
                function_codes.add(preview_function_code)

        if len(function_codes) > 1:
            codes = "、".join(sorted(function_codes))
            raise CodeConflictError(f"同一软件、板卡或产品存在多个历史功能码：{codes}")
        return next(
            iter(function_codes),
            self.configured_subject_function_code(project, standard_name),
        )

    async def generate_one(
        self,
        project: Project,
        original_name: str,
        actor: User,
        source: str,
        enabled: bool,
    ) -> tuple[FileCode, bool]:
        generated = await self.preview_number(
            original_name,
            project,
            check_existing=False,
        )
        return self.persist_generated(
            project,
            generated,
            actor,
            source,
            enabled,
        )

    def persist_generated(
        self,
        project: Project,
        generated: GeneratedNumber,
        actor: User,
        source: str,
        enabled: bool,
    ) -> tuple[FileCode, bool]:
        existing = self.db.scalar(
            select(FileCode).where(
                FileCode.project_id == project.id,
                FileCode.standard_name == generated.standard_name,
            )
        )
        if existing:
            return existing, False

        final_code_existing = self.db.scalar(
            select(FileCode).where(FileCode.final_code == generated.final_code)
        )
        if final_code_existing:
            raise CodeConflictError(
                f"编码 {generated.final_code} 已被文件“{final_code_existing.standard_name}”占用"
            )
        self.reserve_code(project.id, generated.final_code)
        record = self._to_record(generated, project, actor, source, enabled)
        self.db.add(record)
        self.db.flush()
        return record, True

    async def preview_number(
        self,
        original_name: str,
        project: Project,
        exclude_batch_item_id: int | None = None,
        check_existing: bool = True,
    ) -> GeneratedNumber:
        correction = await self.name_correction.correct(
            original_name,
            project.project_code,
        )
        required_function_code = self.required_function_code(
            project.id,
            correction.standard_name,
            exclude_batch_item_id=exclude_batch_item_id,
        )
        if self._batch_state is not None:
            unavailable_final_codes = self._batch_state.unavailable_codes
        else:
            unavailable_final_codes = set(self.db.scalars(select(CodeReservation.final_code)))
            unavailable_final_codes.update(self.db.scalars(select(FileCode.final_code)))
        generated = self.numbering.generate(
            original_name,
            correction,
            project.project_code,
            unavailable_final_codes=unavailable_final_codes,
            required_function_code=required_function_code,
        )
        if check_existing:
            if self._batch_state is not None:
                existing_code = self._batch_state.existing_codes_by_name.get(
                    generated.standard_name
                )
                existing = existing_code is not None
            else:
                record = self.db.scalar(
                    select(FileCode).where(
                        FileCode.project_id == project.id,
                        FileCode.standard_name == generated.standard_name,
                    )
                )
                existing = record is not None
                existing_code = record.final_code if record else None
            if existing:
                raise CodeConflictError(
                    f"文件“{generated.standard_name}”已存在编码"
                    + (f" {existing_code}" if existing_code else "")
                )
            reservation_exists = (
                generated.final_code in self._batch_state.unavailable_codes
                if self._batch_state is not None
                else self.db.get(CodeReservation, generated.final_code) is not None
            )
            if reservation_exists:
                raise CodeConflictError(f"编码 {generated.final_code} 已被全局占用")

        if check_existing:
            if self._batch_state is not None:
                if generated.standard_name in self._batch_state.staged_names:
                    raise CodeConflictError(
                        f"文件“{generated.standard_name}”已在待确认列表中"
                    )
            else:
                staged_items = self.db.scalars(
                    select(ProjectBatchItem).where(
                        ProjectBatchItem.project_id == project.id,
                        ProjectBatchItem.success.is_(True),
                        ProjectBatchItem.file_code_id.is_(None),
                    )
                )
                for item in staged_items:
                    if item.id == exclude_batch_item_id or not item.preview_data:
                        continue
                    if item.preview_data.get("standard_name") == generated.standard_name:
                        raise CodeConflictError(
                            f"文件“{generated.standard_name}”已在待确认列表中"
                        )
        return generated

    async def stage_one(
        self,
        project: Project,
        original_name: str,
    ) -> tuple[ProjectBatchItem, GeneratedNumber]:
        generated = await self.preview_number(original_name, project)
        batch_item = self.stage_generated(project, original_name, generated)
        return batch_item, generated

    def stage_generated(
        self,
        project: Project,
        original_name: str,
        generated: GeneratedNumber,
    ) -> ProjectBatchItem:
        self.reserve_code(project.id, generated.final_code)
        batch_item = ProjectBatchItem(
            project_id=project.id,
            original_name=original_name,
            success=True,
            preview_data=asdict(generated),
            preview_final_code=generated.final_code,
        )
        self.db.add(batch_item)
        self.db.flush()
        return batch_item

    async def generate_batch(
        self,
        project: Project,
        original_names: list[str],
    ) -> list[BatchItemOut]:
        results: list[BatchItemOut] = []
        self._batch_state = _BatchState(self, project)
        try:
            for original_name in original_names:
                try:
                    with self.db.begin_nested():
                        batch_item, generated = await self.stage_one(project, original_name)
                        self.db.flush()
                    self._batch_state.staged_names.add(generated.standard_name)
                    self._batch_state.unavailable_codes.add(generated.final_code)
                    subject_key = self.function_subject_key(project, generated.standard_name)
                    if subject_key and generated.segment_d:
                        self._batch_state.function_codes_by_subject[subject_key].add(
                            (
                                normalized_standard_name(generated.standard_name),
                                generated.segment_d,
                            )
                        )
                    results.append(
                        BatchItemOut(
                            id=batch_item.id,
                            original_name=original_name,
                            success=True,
                            standard_name=generated.standard_name,
                            final_code=generated.final_code,
                        )
                    )
                except CodeConflictError as exc:
                    batch_item = ProjectBatchItem(
                        project_id=project.id,
                        original_name=original_name,
                        success=False,
                        error=f"已重复：{exc}",
                    )
                    self.db.add(batch_item)
                    self.db.flush()
                    results.append(
                        BatchItemOut(
                            id=batch_item.id,
                            original_name=original_name,
                            success=False,
                            error=batch_item.error,
                        )
                    )
                except Exception as exc:
                    batch_item = ProjectBatchItem(
                        project_id=project.id,
                        original_name=original_name,
                        success=False,
                        error=str(exc),
                    )
                    self.db.add(batch_item)
                    self.db.flush()
                    results.append(
                        BatchItemOut(
                            id=batch_item.id,
                            original_name=original_name,
                            success=False,
                            error=str(exc),
                        )
                    )
            self.db.commit()
            return results
        except BaseException:
            self.db.rollback()
            raise
        finally:
            self._batch_state = None

    def persist_preview(
        self,
        project: Project,
        batch_item: ProjectBatchItem,
        actor: User,
    ) -> FileCode:
        if not batch_item.preview_data:
            raise ValueError("待确认编码数据不完整，请重新生成")
        try:
            generated = GeneratedNumber(**batch_item.preview_data)
        except (KeyError, TypeError) as exc:
            raise ValueError("待确认编码数据不完整，请重新生成") from exc

        existing = self.db.scalar(
            select(FileCode).where(
                FileCode.project_id == project.id,
                FileCode.standard_name == generated.standard_name,
            )
        )
        if existing:
            raise CodeConflictError(
                f"文件“{generated.standard_name}”已存在编码 {existing.final_code}"
            )
        final_code_existing = self.db.scalar(
            select(FileCode).where(FileCode.final_code == generated.final_code)
        )
        if final_code_existing:
            raise CodeConflictError(
                f"编码 {generated.final_code} 已被文件“{final_code_existing.standard_name}”占用"
            )
        reservation = self.db.get(CodeReservation, generated.final_code)
        if not reservation:
            self.reserve_code(project.id, generated.final_code)
        elif reservation.project_id != project.id:
            raise CodeConflictError(f"编码 {generated.final_code} 已被其他项目全局占用")

        record = self._to_record(
            generated,
            project,
            actor,
            source="admin_batch",
            enabled=True,
        )
        self.db.add(record)
        self.db.flush()
        batch_item.file_code_id = record.id
        return record

    def reserve_code(self, project_id: int, final_code: str) -> CodeReservation:
        if self._batch_state is not None:
            if final_code in self._batch_state.unavailable_codes:
                raise CodeConflictError(f"编码 {final_code} 已被全局占用")
            reservation = CodeReservation(final_code=final_code, project_id=project_id)
            self.db.add(reservation)
            self.db.flush()
            return reservation

        existing = self.db.get(CodeReservation, final_code)
        if existing:
            raise CodeConflictError(f"编码 {final_code} 已被全局占用")
        reservation = CodeReservation(
            final_code=final_code,
            project_id=project_id,
        )
        self.db.add(reservation)
        self.db.flush()
        return reservation

    @staticmethod
    def _to_record(
        generated: GeneratedNumber,
        project: Project,
        actor: User,
        source: str,
        enabled: bool,
    ) -> FileCode:
        return FileCode(
            project_id=project.id,
            original_name=generated.original_name,
            standard_name=generated.standard_name,
            segment_a=generated.segment_a,
            segment_b=generated.segment_b,
            segment_c=generated.segment_c,
            segment_d=generated.segment_d,
            segment_e=generated.segment_e,
            segment_f=generated.segment_f,
            segment_g=generated.segment_g,
            segment_h=generated.segment_h,
            final_code=generated.final_code,
            source=source,
            enabled=enabled,
            created_by_id=actor.id,
        )
