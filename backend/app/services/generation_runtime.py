from collections.abc import Iterable

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.briefs import Brief
from app.models.generation_tasks import GenerationTask
from app.services.briefs.contracts import BriefContentItem, StructuredBrief
from app.services.generation_worker import StepExecutionResult
from app.services.renderers.excel.contracts import WorkbookPlan
from app.services.renderers.presentation.contracts import PresentationPlan


class BriefPlanCompilationError(ValueError):
    pass


class StructuredBriefPlanCompiler:
    _content_limit = 480
    _elements_per_slide = 4
    _maximum_content_slides = 28
    _workbook_cell_text_limit = 500

    def presentation(
        self,
        brief: StructuredBrief,
        *,
        template_code: str,
        revision: int,
    ) -> PresentationPlan:
        entries = self._entries(brief)
        evidence_ids = self._evidence_ids(entries)
        if not evidence_ids:
            raise BriefPlanCompilationError("generation_evidence_required")
        evidence_entries = [entry for entry in entries if entry.item.evidence_ids]
        user_entries = [entry for entry in entries if not entry.item.evidence_ids]
        slides = [
            {
                "layout": "title",
                "title": self._title(brief, "pptx"),
                "subtitle": brief.audience[:500],
                "speaker_notes": ["Office AI 根据已确认 Brief 生成。"],
                "elements": [],
            }
        ]
        for offset in range(0, len(evidence_entries), self._elements_per_slide):
            batch = evidence_entries[offset : offset + self._elements_per_slide]
            elements = []
            for index, entry in enumerate(batch):
                if len(entry.item.evidence_ids) > 100:
                    raise BriefPlanCompilationError(
                        "presentation_evidence_reference_limit_exceeded"
                    )
                elements.append(
                    {
                        "type": "text",
                        "text": entry.item.content,
                        "evidence_ids": list(entry.item.evidence_ids),
                        "x": 0.9,
                        "y": 1.35 + 1.35 * index,
                        "w": 11.5,
                        "h": 1.0,
                    }
                )
            slides.append(
                {
                    "layout": "content",
                    "title": self._section_title(batch[0].kind),
                    "speaker_notes": ["内容引用已确认 Brief 的 Evidence。"],
                    "elements": elements,
                }
            )
        for entry in user_entries:
            slides.append(
                {
                    "layout": "section",
                    "title": entry.item.content,
                    "speaker_notes": ["用户明确要求，不声明文件 Evidence。"],
                    "elements": [],
                }
            )
        slides.append(
            {
                "layout": "closing",
                "title": "结论与下一步",
                "speaker_notes": ["请结合质量检查结果复核并下载。"],
                "elements": [],
            }
        )
        if len(slides) > 30:
            raise BriefPlanCompilationError("presentation_slide_limit_exceeded")
        return PresentationPlan.validate_for_renderer(
            {
                "schema_version": "presentation-plan.v1",
                "renderer_version": "ppt-renderer.v1",
                "template": {"code": template_code, "version": "1.0.0"},
                "locale": "zh-CN",
                "metadata": self._metadata(
                    self._title(brief, "pptx"), brief.goal, revision
                ),
                "evidence_ids": evidence_ids,
                "images": {},
                "data_sources": {},
                "slides": slides,
            }
        )

    def workbook(
        self,
        brief: StructuredBrief,
        *,
        template_code: str,
        revision: int,
    ) -> WorkbookPlan:
        entries = self._entries(brief)
        evidence_ids = self._evidence_ids(entries)
        if not evidence_ids:
            raise BriefPlanCompilationError("generation_evidence_required")
        rows = []
        for entry in entries:
            rows.extend(
                {
                    "category": self._category(entry.kind),
                    "content": entry.item.content,
                    "evidence_refs": references,
                }
                for references in self._workbook_reference_cells(
                    entry.item.evidence_ids
                )
            )
        return WorkbookPlan.validate_for_renderer(
            {
                "schema_version": "workbook-plan.v1",
                "renderer_version": "excel-renderer.v1",
                "template": {"code": template_code, "version": "1.0.0"},
                "locale": "zh-CN",
                "metadata": self._metadata(
                    self._title(brief, "xlsx"), brief.goal, revision
                ),
                "evidence_ids": evidence_ids,
                "sheets": [
                    {
                        "kind": "data",
                        "name": "分析依据",
                        "title": self._title(brief, "xlsx"),
                        "columns": [
                            {
                                "key": "category",
                                "header": "类型",
                                "value_type": "text",
                            },
                            {
                                "key": "content",
                                "header": "内容",
                                "value_type": "text",
                            },
                            {
                                "key": "evidence_refs",
                                "header": "Evidence",
                                "value_type": "text",
                            },
                        ],
                        "computed_columns": [],
                        "rows": rows,
                        "conditional_formats": [],
                        "data_validations": [],
                        "freeze_panes": {"row": 2, "column": 0},
                        "print_settings": {
                            "orientation": "landscape",
                            "fit_width": 1,
                            "fit_height": 0,
                            "repeat_header": True,
                        },
                    }
                ],
            }
        )

    def _entries(self, brief: StructuredBrief) -> list["_PlanEntry"]:
        source = (
            ("fact", brief.facts),
            ("inference", brief.inferences),
            ("requirement", brief.must_include),
        )
        entries = [
            _PlanEntry(kind, piece)
            for kind, items in source
            for item in items
            for piece in self._split(item)
        ]
        if not entries:
            raise BriefPlanCompilationError("generation_brief_content_required")
        if (
            len(entries) + self._elements_per_slide - 1
        ) // self._elements_per_slide > self._maximum_content_slides:
            raise BriefPlanCompilationError("generation_plan_content_limit_exceeded")
        return entries

    def _split(self, item: BriefContentItem) -> Iterable[BriefContentItem]:
        content = item.content
        for offset in range(0, len(content), self._content_limit):
            yield item.model_copy(
                update={"content": content[offset : offset + self._content_limit]}
            )

    @staticmethod
    def _evidence_ids(entries: list["_PlanEntry"]) -> list[str]:
        return list(
            dict.fromkeys(
                evidence_id
                for entry in entries
                for evidence_id in entry.item.evidence_ids
            )
        )

    @classmethod
    def _workbook_reference_cells(cls, evidence_ids: tuple[str, ...]) -> list[str]:
        cells = []
        current = ""
        for evidence_id in evidence_ids:
            candidate = f"{current},{evidence_id}" if current else evidence_id
            if len(candidate) > cls._workbook_cell_text_limit:
                if not current:
                    raise BriefPlanCompilationError(
                        "workbook_evidence_reference_limit_exceeded"
                    )
                cells.append(current)
                current = evidence_id
            else:
                current = candidate
        cells.append(current)
        return cells

    @staticmethod
    def _title(brief: StructuredBrief, kind: str) -> str:
        return next(
            item.title for item in brief.output_plan.deliverables if item.kind == kind
        )

    @staticmethod
    def _metadata(title: str, subject: str, revision: int) -> dict:
        return {
            "title": title[:500],
            "subject": subject[:500],
            "author": "Office AI",
            "company": "Office AI",
            "revision": str(revision),
        }

    @staticmethod
    def _section_title(kind: str) -> str:
        return {
            "fact": "核心事实",
            "inference": "经营洞察",
            "requirement": "必须包含",
        }[kind]

    @staticmethod
    def _category(kind: str) -> str:
        return {
            "fact": "事实",
            "inference": "推断",
            "requirement": "必须包含",
        }[kind]


class _GenerationPipeline:
    output_kind: str

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        output_service,
        quality_service,
        *,
        compiler: StructuredBriefPlanCompiler | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._output = output_service
        self._quality = quality_service
        self._compiler = compiler or StructuredBriefPlanCompiler()

    async def execute(self, context):
        try:
            brief, template_code = await self._load_brief(context.task_id)
            plan = self._compile(
                StructuredBrief.model_validate(brief.content),
                template_code=template_code,
                revision=brief.revision,
            )
        except BriefPlanCompilationError as error:
            return StepExecutionResult.permanent_failure(str(error))
        except ValidationError:
            return StepExecutionResult.permanent_failure("generation_brief_invalid")
        output = await self._output.render(
            context.task_id,
            context.step_id,
            self._output_payload(plan),
        )
        quality = await self._quality.evaluate(output.asset_id, context.step_id, plan)
        return quality.step_result()

    def _output_payload(self, plan):
        return plan

    async def _load_brief(self, task_id) -> tuple[Brief, str]:
        async with self._session_factory() as session:
            task = await session.get(GenerationTask, task_id)
            brief = (
                await session.get(Brief, task.brief_id) if task is not None else None
            )
        if task is None or brief is None:
            raise BriefPlanCompilationError("generation_brief_missing")
        frozen = [
            item for item in task.skill_snapshot if item.get("kind") == self.output_kind
        ]
        if (
            len(frozen) != 1
            or frozen[0].get("template_version") != "1.0.0"
            or not isinstance(frozen[0].get("template_code"), str)
        ):
            raise BriefPlanCompilationError("generation_template_snapshot_invalid")
        return brief, frozen[0]["template_code"]

    def _compile(
        self,
        brief: StructuredBrief,
        *,
        template_code: str,
        revision: int,
    ):
        raise NotImplementedError


class PresentationGenerationPipeline(_GenerationPipeline):
    output_kind = "pptx"

    def _output_payload(self, plan: PresentationPlan) -> dict:
        return plan.model_dump(mode="json", exclude_none=True)

    def _compile(
        self,
        brief: StructuredBrief,
        *,
        template_code: str,
        revision: int,
    ) -> PresentationPlan:
        return self._compiler.presentation(
            brief,
            template_code=template_code,
            revision=revision,
        )


class SpreadsheetGenerationPipeline(_GenerationPipeline):
    output_kind = "xlsx"

    def _compile(
        self,
        brief: StructuredBrief,
        *,
        template_code: str,
        revision: int,
    ) -> WorkbookPlan:
        return self._compiler.workbook(
            brief,
            template_code=template_code,
            revision=revision,
        )


class _PlanEntry:
    def __init__(self, kind: str, item: BriefContentItem) -> None:
        self.kind = kind
        self.item = item
