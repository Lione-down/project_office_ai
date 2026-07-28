from uuid import UUID

from app.models.briefs import Brief
from app.models.generation_tasks import GenerationTask
from app.services.evidence.contracts import EvidenceItem
from app.services.generation_runtime import (
    PresentationGenerationPipeline,
    SpreadsheetGenerationPipeline,
)
from app.services.generation_worker import (
    GenerationWorkerService,
    StepExecutionContext,
    StepExecutionResult,
)
from app.services.briefs.contracts import StructuredBrief
from app.services.generation_runtime import StructuredBriefPlanCompiler
from tests.generation.conftest import BRIEF_ID


EVIDENCE_A = f"e-{'a' * 64}"
EVIDENCE_B = f"e-{'b' * 64}"


def excel_evidence(cell: str, value: str, evidence_id: str) -> EvidenceItem:
    return EvidenceItem.model_validate(
        {
            "evidence_id": evidence_id,
            "evidence_type": "source_fact",
            "asset_id": "019fa500-0000-7000-8000-000000000001",
            "asset_version": f"sha256:{'c' * 64}",
            "location": {
                "kind": "excel_cell",
                "sheet": "经营概览",
                "cell": cell,
            },
            "raw_value": value,
            "normalized_value": value,
            "value_kind": "narrative",
            "unit": None,
            "currency": None,
            "ocr_confidence": None,
            "parser_name": "openpyxl",
            "parser_version": "1.0.0",
            "ocr_engine_name": None,
            "ocr_engine_version": None,
            "warnings": [],
            "calculation_blocked": False,
            "calculation_expression": None,
            "inference_model": None,
        }
    )


def structured_brief() -> StructuredBrief:
    return StructuredBrief.model_validate(
        {
            "module": "combined",
            "goal": "形成可复核的销售经营结论",
            "audience": "经营管理层",
            "language": "zh-CN",
            "domain": "sales",
            "tone": "professional",
            "source_asset_versions": [
                {
                    "asset_id": str(UUID("019fa500-0000-7000-8000-000000000001")),
                    "asset_version": f"sha256:{'c' * 64}",
                }
            ],
            "term_library_versions": [],
            "selected_skills": [
                {
                    "skill_code": "ppt.sales-business-review.v1",
                    "version": "1.0.0",
                },
                {
                    "skill_code": "excel.sales-analysis-dashboard.v1",
                    "version": "1.0.0",
                },
            ],
            "selected_model": {
                "model_id": str(UUID("019fa500-0000-7000-8000-000000000002")),
                "provider_id": str(UUID("019fa500-0000-7000-8000-000000000003")),
                "credential_id": str(UUID("019fa500-0000-7000-8000-000000000004")),
                "model_code": "agnes-2.0-flash",
            },
            "output_plan": {
                "deliverables": [
                    {
                        "kind": "pptx",
                        "title": "销售经营汇报",
                        "source": "user",
                        "evidence_ids": [],
                    },
                    {
                        "kind": "xlsx",
                        "title": "销售经营分析",
                        "source": "user",
                        "evidence_ids": [],
                    },
                ]
            },
            "facts": [
                {
                    "content": "华东区域销售额保持领先",
                    "source": "file",
                    "evidence_ids": [EVIDENCE_A],
                },
                {
                    "content": "重点产品复购率改善",
                    "source": "calculation",
                    "evidence_ids": [EVIDENCE_B],
                },
            ],
            "inferences": [
                {
                    "content": "应优先复制华东区域的销售打法",
                    "source": "agnes_inference",
                    "evidence_ids": [EVIDENCE_A, EVIDENCE_B],
                }
            ],
            "unresolved_items": [],
            "must_include": [],
            "must_exclude": [],
            "citation_policy": {
                "internal_tracking": True,
                "visible_citations": True,
            },
        }
    )


def test_compiler_builds_strict_presentation_plan_from_confirmed_brief() -> None:
    plan = StructuredBriefPlanCompiler().presentation(
        structured_brief(),
        template_code="ppt.executive-blue.v1",
        revision=2,
    )

    assert plan.template.code == "ppt.executive-blue.v1"
    assert plan.metadata.revision == "2"
    assert plan.evidence_ids == [EVIDENCE_A, EVIDENCE_B]
    assert len(plan.slides) >= 3
    rendered_text = [
        element.text
        for slide in plan.slides
        for element in slide.elements
        if element.type == "text"
    ]
    assert "华东区域销售额保持领先" in rendered_text
    assert "重点产品复购率改善" in rendered_text
    assert "应优先复制华东区域的销售打法" in rendered_text


def test_compiler_deduplicates_presentation_element_evidence_refs() -> None:
    brief = structured_brief()
    inference = brief.inferences[0].model_copy(
        update={"evidence_ids": (EVIDENCE_A, EVIDENCE_A, EVIDENCE_B)}
    )

    plan = StructuredBriefPlanCompiler().presentation(
        brief.model_copy(update={"inferences": (inference,)}),
        template_code="ppt.executive-blue.v1",
        revision=2,
    )

    inference_element = next(
        element
        for slide in plan.slides
        for element in slide.elements
        if element.type == "text" and element.text == inference.content
    )
    assert inference_element.evidence_ids == [EVIDENCE_A, EVIDENCE_B]


def test_compiler_builds_management_report_structure_from_excel_evidence() -> None:
    values = (
        ("A1", "指标"),
        ("B1", "一月"),
        ("C1", "二月"),
        ("A2", "任务量"),
        ("B2", "20.056999999999999"),
        ("C2", "135"),
        ("A3", "完成量"),
        ("B3", "118"),
        ("C3", "142"),
    )
    evidence_items = tuple(
        excel_evidence(cell, value, f"e-{index:064x}")
        for index, (cell, value) in enumerate(values, start=1)
    )

    plan = StructuredBriefPlanCompiler().presentation(
        structured_brief(),
        template_code="ppt.operating-review.v1",
        revision=2,
        evidence_items=evidence_items,
    )

    assert len(plan.slides) >= 6
    assert any(slide.title == "目录" for slide in plan.slides)
    assert any(
        element.type == "table" for slide in plan.slides for element in slide.elements
    )
    assert any(source.kind == "table" for source in plan.data_sources.values())
    assert any(
        "20.057" in row
        for source in plan.data_sources.values()
        if source.kind == "table"
        for row in source.rows
    )
    assert all(
        "[Evidence:" not in element.text
        for slide in plan.slides
        for element in slide.elements
        if element.type in {"text", "source"}
    )


def test_first_table_page_does_not_show_redundant_page_one_suffix() -> None:
    values = [("A1", "指标"), ("B1", "数量")]
    values.extend(
        (cell, value)
        for row in range(2, 14)
        for cell, value in ((f"A{row}", f"项目{row - 1}"), (f"B{row}", str(row)))
    )
    evidence_items = tuple(
        excel_evidence(cell, value, f"e-{index:064x}")
        for index, (cell, value) in enumerate(values, start=1)
    )

    plan = StructuredBriefPlanCompiler().presentation(
        structured_brief(),
        template_code="ppt.operating-review.v1",
        revision=2,
        evidence_items=evidence_items,
    )

    table_slide = next(
        slide
        for slide in plan.slides
        if any(element.type == "table" for element in slide.elements)
    )

    assert not table_slide.title.endswith("（1）")


def test_data_first_sheet_uses_generic_headers_without_dropping_first_row() -> None:
    values = (
        ("A1", "制高点开拓"),
        ("A2", "1"),
        ("B2", "黄良锦"),
        ("C2", "GZ13260"),
        ("D2", "同兴羊蹄煲"),
        ("A3", "2"),
        ("B3", "黄良锦"),
        ("C3", "GZ13320"),
        ("D3", "一兴田鱼鸡子牛蹄煲"),
    )
    evidence_items = tuple(
        excel_evidence(cell, value, f"e-{index:064x}")
        for index, (cell, value) in enumerate(values, start=1)
    )

    plan = StructuredBriefPlanCompiler().presentation(
        structured_brief(),
        template_code="ppt.operating-review.v1",
        revision=2,
        evidence_items=evidence_items,
    )
    table = next(
        source for source in plan.data_sources.values() if source.kind == "table"
    )

    assert table.columns == ["序号", "指标1", "指标2", "指标3"]
    assert table.rows[0] == ["1", "黄良锦", "GZ13260", "同兴羊蹄煲"]


def test_compiler_builds_text_only_workbook_without_inventing_numbers() -> None:
    plan = StructuredBriefPlanCompiler().workbook(
        structured_brief(),
        template_code="excel.analysis-dashboard.v1",
        revision=2,
    )

    assert plan.template.code == "excel.analysis-dashboard.v1"
    assert plan.evidence_ids == [EVIDENCE_A, EVIDENCE_B]
    assert len(plan.sheets) == 1
    sheet = plan.sheets[0]
    assert sheet.kind == "data"
    assert {column.value_type for column in sheet.columns} == {"text"}
    assert sheet.computed_columns == []
    assert [row["content"] for row in sheet.rows] == [
        "华东区域销售额保持领先",
        "重点产品复购率改善",
        "应优先复制华东区域的销售打法",
    ]


def test_compiler_groups_many_workbook_evidence_references_without_loss() -> None:
    evidence_ids = tuple(f"e-{index:064x}" for index in range(21))
    brief = structured_brief()
    fact = brief.facts[0].model_copy(update={"evidence_ids": evidence_ids})
    plan = StructuredBriefPlanCompiler().workbook(
        brief.model_copy(
            update={
                "facts": (fact,),
                "inferences": (),
                "must_include": (),
            }
        ),
        template_code="excel.analysis-dashboard.v1",
        revision=2,
    )

    cells = [row["evidence_refs"] for row in plan.sheets[0].rows]

    assert all(len(cell) <= 500 for cell in cells)
    assert (
        tuple(
            evidence_id
            for cell in cells
            for evidence_id in cell.split(",")
            if evidence_id
        )
        == evidence_ids
    )


class RecordingOutput:
    def __init__(self) -> None:
        self.calls = []

    async def render(self, task_id, step_id, plan):
        self.calls.append((task_id, step_id, plan))
        return type(
            "Output",
            (),
            {
                "asset_id": UUID("019fa500-0000-7000-8000-000000000010"),
            },
        )()


class RecordingQuality:
    def __init__(self) -> None:
        self.calls = []

    async def evaluate(self, asset_id, step_id, plan):
        self.calls.append((asset_id, step_id, plan))
        return type(
            "Outcome",
            (),
            {
                "step_result": lambda _self: StepExecutionResult.succeeded(
                    output_asset_id=asset_id,
                    asset_version=f"sha256:{'d' * 64}",
                    quality_status="passed",
                    download_allowed=True,
                    quality_report_schema_version="presentation-quality-report.v1",
                )
            },
        )()


class ContractValidatingPresentationQuality(RecordingQuality):
    async def evaluate(self, asset_id, step_id, plan):
        assert isinstance(plan, dict)
        return await super().evaluate(asset_id, step_id, plan)


async def test_presentation_pipeline_loads_frozen_brief_and_runs_quality(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "runtime-presentation-001"
    )
    async with generation_harness.session_factory() as session, session.begin():
        brief = await session.get(Brief, BRIEF_ID, with_for_update=True)
        brief.content = structured_brief().model_dump(mode="json")
    output = RecordingOutput()
    quality = ContractValidatingPresentationQuality()
    pipeline = PresentationGenerationPipeline(
        generation_harness.session_factory,
        output,
        quality,
    )
    context = StepExecutionContext(
        task_id=created.task_id,
        step_id=created.steps[0].step_key
        and UUID("019fa500-0000-7000-8000-000000000011"),
        step_key="render:pptx",
        output_kind="pptx",
        attempt=1,
        model_snapshot={},
    )

    result = await pipeline.execute(context)

    assert result.status == "succeeded"
    assert isinstance(output.calls[0][2], dict)
    assert output.calls[0][2]["template"]["code"] == "ppt.executive-blue.v1"
    assert quality.calls[0][2]["template"]["code"] == "ppt.executive-blue.v1"


async def test_spreadsheet_pipeline_loads_frozen_brief_without_numeric_guessing(
    generation_harness,
) -> None:
    await generation_harness.set_combined()
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "runtime-spreadsheet-001"
    )
    async with generation_harness.session_factory() as session, session.begin():
        brief = await session.get(Brief, BRIEF_ID, with_for_update=True)
        brief.content = structured_brief().model_dump(mode="json")
    output = RecordingOutput()
    quality = RecordingQuality()
    pipeline = SpreadsheetGenerationPipeline(
        generation_harness.session_factory,
        output,
        quality,
    )
    context = StepExecutionContext(
        task_id=created.task_id,
        step_id=UUID("019fa500-0000-7000-8000-000000000012"),
        step_key="render:xlsx",
        output_kind="xlsx",
        attempt=1,
        model_snapshot={},
    )

    result = await pipeline.execute(context)

    assert result.status == "succeeded"
    plan = output.calls[0][2]
    assert plan.template.code == "excel.analysis-dashboard.v1"
    assert {column.value_type for column in plan.sheets[0].columns} == {"text"}


async def test_pipeline_rejects_empty_brief_without_rendering(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "runtime-empty-brief-001"
    )
    empty_brief = structured_brief().model_copy(
        update={"facts": (), "inferences": (), "must_include": ()}
    )
    async with generation_harness.session_factory() as session, session.begin():
        brief = await session.get(Brief, BRIEF_ID, with_for_update=True)
        brief.content = empty_brief.model_dump(mode="json")
    output = RecordingOutput()
    pipeline = PresentationGenerationPipeline(
        generation_harness.session_factory,
        output,
        RecordingQuality(),
    )
    context = StepExecutionContext(
        task_id=created.task_id,
        step_id=UUID("019fa500-0000-7000-8000-000000000013"),
        step_key="render:pptx",
        output_kind="pptx",
        attempt=1,
        model_snapshot={},
    )

    result = await pipeline.execute(context)

    assert result.status == "permanent_failure"
    assert result.error_category == "generation_brief_content_required"
    assert output.calls == []


class AllowAllCredentialLimiter:
    async def acquire(self, **_values) -> bool:
        return True


class ProgressRecordingExecutor:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self.observed = []

    async def execute(self, context):
        async with self._session_factory() as session:
            task = await session.get(GenerationTask, context.task_id)
            self.observed.append(task.progress)
        return StepExecutionResult.succeeded()


async def test_worker_persists_stage_progress_before_and_between_outputs(
    generation_harness,
) -> None:
    await generation_harness.set_combined()
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "runtime-progress-001"
    )
    executor = ProgressRecordingExecutor(generation_harness.session_factory)

    completed = await GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(created.task_id, executor)

    assert executor.observed == [10, 55]
    assert completed.progress == 100
