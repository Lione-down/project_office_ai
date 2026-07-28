from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import islice

from openpyxl.utils.cell import coordinate_to_tuple

from app.services.briefs.contracts import StructuredBrief
from app.services.evidence.contracts import EvidenceItem, ExcelCellLocation
from app.services.renderers.presentation.contracts import PresentationPlan


@dataclass(frozen=True)
class _TableSection:
    title: str
    columns: list[str]
    rows: list[list[str]]
    evidence_ids: list[str]


class ManagementPresentationComposer:
    _maximum_table_slides = 22
    _maximum_columns = 8
    _maximum_rows = 10
    _maximum_cell_characters = 80
    _header_markers = (
        "指标",
        "业务员",
        "姓名",
        "品种",
        "品号",
        "产品",
        "客户",
        "区域",
        "门店",
        "渠道",
        "日期",
        "时间",
        "月份",
        "数量",
        "销量",
        "金额",
        "任务",
        "完成",
        "同比",
        "环比",
        "编码",
        "代码",
        "内容",
        "类型",
    )

    def compose(
        self,
        brief: StructuredBrief,
        *,
        template_code: str,
        revision: int,
        evidence_items: tuple[EvidenceItem, ...],
    ) -> PresentationPlan | None:
        sections = self._table_sections(evidence_items)
        if not sections:
            return None

        data_sources: dict[str, dict] = {}
        slides = [
            {
                "layout": "title",
                "title": self._title(brief),
                "subtitle": brief.audience[:500],
                "speaker_notes": ["根据已确认 Brief 与冻结业务数据生成。"],
                "elements": [],
            },
            self._contents_slide(sections),
            self._summary_slide(brief),
        ]
        for index, section in enumerate(sections, start=1):
            source_id = f"management-table-{index:02d}"
            data_sources[source_id] = {
                "kind": "table",
                "columns": section.columns,
                "rows": section.rows,
            }
            slides.append(
                {
                    "layout": "content",
                    "title": section.title[:500],
                    "speaker_notes": ["表格来自冻结 Excel Evidence。"],
                    "elements": [
                        {
                            "type": "table",
                            "data_source_id": source_id,
                            "evidence_ids": section.evidence_ids,
                            "x": 0.8,
                            "y": 1.25,
                            "w": 11.7,
                            "h": 5.35,
                        },
                        {
                            "type": "source",
                            "text": "来源：已确认业务数据",
                            "evidence_ids": section.evidence_ids,
                            "x": 0.8,
                            "y": 6.72,
                            "w": 11.7,
                            "h": 0.24,
                        },
                    ],
                }
            )
        slides.extend((self._actions_slide(brief), self._closing_slide(brief)))
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for slide in slides
                for element in slide["elements"]
                for evidence_id in element.get("evidence_ids", [])
            )
        )
        return PresentationPlan.validate_for_renderer(
            {
                "schema_version": "presentation-plan.v1",
                "renderer_version": "ppt-renderer.v1",
                "template": {"code": template_code, "version": "1.0.0"},
                "locale": "zh-CN",
                "metadata": {
                    "title": self._title(brief),
                    "subject": brief.goal[:500],
                    "author": "Office AI",
                    "company": "Office AI",
                    "revision": str(revision),
                },
                "evidence_ids": evidence_ids,
                "images": {},
                "data_sources": data_sources,
                "slides": slides,
            }
        )

    def _table_sections(
        self, evidence_items: tuple[EvidenceItem, ...]
    ) -> list[_TableSection]:
        grouped: dict[tuple[str, str], list[EvidenceItem]] = defaultdict(list)
        for item in evidence_items:
            if isinstance(item.location, ExcelCellLocation):
                grouped[(str(item.asset_id), item.location.sheet)].append(item)
        per_sheet = [
            self._sheet_sections(sheet, items)
            for (_, sheet), items in sorted(grouped.items())
        ]
        selected: list[_TableSection] = []
        while len(selected) < self._maximum_table_slides:
            added = False
            for sections in per_sheet:
                if sections and len(selected) < self._maximum_table_slides:
                    selected.append(sections.pop(0))
                    added = True
            if not added:
                break
        return selected

    def _sheet_sections(
        self, sheet: str, evidence_items: list[EvidenceItem]
    ) -> list[_TableSection]:
        cells: dict[tuple[int, int], EvidenceItem] = {}
        for item in evidence_items:
            row, column = coordinate_to_tuple(item.location.cell)
            cells[(row, column)] = item
        rows = sorted({row for row, _ in cells})
        if len(rows) < 2:
            return []
        candidate_rows = list(islice(rows, 12))
        header_row = max(
            candidate_rows,
            key=lambda row: (sum(key[0] == row for key in cells), -row),
        )
        columns = sorted(
            {
                column
                for row, column in cells
                if row >= header_row and self._value(cells[(row, column)])
            }
        )
        if len(columns) < 2:
            return []
        title = self._sheet_title(sheet, cells, header_row)
        header_values = [
            self._value(cells.get((header_row, column))) for column in columns
        ]
        has_header = any(
            marker in value
            for value in header_values
            for marker in self._header_markers
        )
        data_rows = [
            row
            for row in rows
            if (row > header_row if has_header else row >= header_row)
            and any(self._value(cells.get((row, column))) for column in columns)
        ]
        if not data_rows:
            return []
        column_groups = self._column_groups(columns)
        sections: list[_TableSection] = []
        for group_index, column_group in enumerate(column_groups, start=1):
            headers = (
                [
                    self._value(cells.get((header_row, column))) or f"列{column}"
                    for column in column_group
                ]
                if has_header
                else self._generic_headers(column_group, cells, data_rows)
            )
            for row_offset in range(0, len(data_rows), self._maximum_rows):
                row_group = data_rows[row_offset : row_offset + self._maximum_rows]
                section_rows = [
                    [self._value(cells.get((row, column))) for column in column_group]
                    for row in row_group
                ]
                evidence_ids = [
                    item.evidence_id
                    for row in (
                        *((header_row,) if has_header else ()),
                        *row_group,
                    )
                    for column in column_group
                    if (item := cells.get((row, column))) is not None
                ]
                page_number = len(sections) + 1
                suffix = "" if page_number == 1 else f"（续{page_number - 1}）"
                sections.append(
                    _TableSection(
                        title=f"{title}{suffix}",
                        columns=headers,
                        rows=section_rows,
                        evidence_ids=list(dict.fromkeys(evidence_ids)),
                    )
                )
        return sections

    @classmethod
    def _generic_headers(
        cls,
        columns: list[int],
        cells: dict[tuple[int, int], EvidenceItem],
        data_rows: list[int],
    ) -> list[str]:
        first_values = [
            cls._value(cells.get((row, columns[0]))) for row in data_rows[:5]
        ]
        is_sequence = bool(first_values) and all(
            value.isdigit() for value in first_values
        )
        first_header = "序号" if is_sequence else "项目"
        return [
            first_header if index == 0 else f"指标{index}"
            for index, _ in enumerate(columns)
        ]

    def _column_groups(self, columns: list[int]) -> list[list[int]]:
        if len(columns) <= self._maximum_columns:
            return [columns]
        anchor = columns[0]
        remainder = columns[1:]
        return [
            [anchor, *remainder[offset : offset + self._maximum_columns - 1]]
            for offset in range(0, len(remainder), self._maximum_columns - 1)
        ]

    def _contents_slide(self, sections: list[_TableSection]) -> dict:
        topics = list(
            dict.fromkeys(section.title.split("（", 1)[0] for section in sections)
        )
        text = "\n".join(
            (
                "01  经营摘要",
                *(
                    f"{index:02d}  {topic[:24]}"
                    for index, topic in enumerate(topics[:5], start=2)
                ),
                f"{min(len(topics), 5) + 2:02d}  问题与下一步措施",
            )
        )
        return {
            "layout": "content",
            "title": "目录",
            "speaker_notes": ["目录依据最终生成页面确定。"],
            "elements": [
                {
                    "type": "text",
                    "text": text,
                    "evidence_ids": sections[0].evidence_ids,
                    "x": 1.35,
                    "y": 1.45,
                    "w": 10.6,
                    "h": 4.9,
                }
            ],
        }

    def _summary_slide(self, brief: StructuredBrief) -> dict:
        items = tuple(
            islice(
                (
                    item
                    for item in (*brief.facts, *brief.inferences)
                    if item.evidence_ids
                ),
                3,
            )
        )
        return {
            "layout": "content",
            "title": "经营摘要",
            "speaker_notes": ["摘要来自已确认 Brief。"],
            "elements": [
                {
                    "type": "text",
                    "text": f"{index:02d}  {item.content}",
                    "evidence_ids": list(item.evidence_ids),
                    "x": 1.0,
                    "y": 1.35 + (index - 1) * 1.65,
                    "w": 11.2,
                    "h": 1.3,
                }
                for index, item in enumerate(items, start=1)
            ],
        }

    def _actions_slide(self, brief: StructuredBrief) -> dict:
        candidates = tuple(
            islice(
                (
                    item
                    for item in (*brief.inferences, *brief.must_include)
                    if item.evidence_ids
                ),
                3,
            )
        )
        if not candidates:
            candidates = tuple(item for item in brief.facts if item.evidence_ids)[:1]
        return {
            "layout": "content",
            "title": "问题与下一步措施",
            "speaker_notes": ["行动项来自已确认 Brief，不扩展未确认因果。"],
            "elements": [
                {
                    "type": "text",
                    "text": f"{index:02d}  {item.content}",
                    "evidence_ids": list(item.evidence_ids),
                    "x": 1.0,
                    "y": 1.45 + (index - 1) * 1.65,
                    "w": 11.2,
                    "h": 1.3,
                }
                for index, item in enumerate(candidates, start=1)
            ],
        }

    def _closing_slide(self, brief: StructuredBrief) -> dict:
        return {
            "layout": "closing",
            "title": "总结与下一步",
            "subtitle": brief.goal[:500],
            "speaker_notes": ["请结合质量检查结果复核后下载。"],
            "elements": [],
        }

    @staticmethod
    def _sheet_title(
        sheet: str, cells: dict[tuple[int, int], EvidenceItem], header_row: int
    ) -> str:
        preceding = [
            ManagementPresentationComposer._value(item)
            for (row, _), item in sorted(cells.items())
            if row < header_row
        ]
        return next((value for value in preceding if value), sheet)[:80]

    @classmethod
    def _value(cls, item: EvidenceItem | None) -> str:
        if item is None:
            return ""
        value = (item.normalized_value or item.raw_value).strip()
        value = cls._format_numeric_artifact(value)
        if len(value) > cls._maximum_cell_characters:
            return f"{value[: cls._maximum_cell_characters - 1]}…"
        return value

    @staticmethod
    def _format_numeric_artifact(value: str) -> str:
        if "." not in value and "e" not in value.lower():
            return value
        if len(value) > 128:
            return value
        try:
            number = Decimal(value)
            rounded = number.quantize(Decimal("0.0001"))
        except InvalidOperation:
            return value
        if not number.is_finite():
            return value
        formatted = format(rounded.normalize(), "f")
        return "0" if Decimal(formatted) == 0 else formatted

    @staticmethod
    def _title(brief: StructuredBrief) -> str:
        return next(
            item.title for item in brief.output_plan.deliverables if item.kind == "pptx"
        )
