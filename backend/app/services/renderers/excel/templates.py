from dataclasses import dataclass


@dataclass(frozen=True)
class ExcelTemplate:
    code: str
    version: str
    title_format: dict
    header_format: dict
    text_format: dict
    number_format: dict
    integer_format: dict
    percent_format: dict
    metric_label_format: dict
    metric_value_format: dict
    negative_format: dict
    chart_style: int
    tab_color: str


_TEMPLATES = {
    ("excel.analysis-dashboard.v1", "1.0.0"): ExcelTemplate(
        code="excel.analysis-dashboard.v1",
        version="1.0.0",
        title_format={
            "bold": True,
            "font_size": 16,
            "font_color": "#FFFFFF",
            "bg_color": "#24527A",
            "align": "left",
            "valign": "vcenter",
        },
        header_format={
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#3578A8",
            "border": 1,
            "align": "center",
        },
        text_format={"border": 1, "font_color": "#18212B"},
        number_format={"border": 1, "num_format": "#,##0.00"},
        integer_format={"border": 1, "num_format": "0"},
        percent_format={"border": 1, "num_format": "0.00%"},
        metric_label_format={
            "bold": True,
            "bg_color": "#DCEAF5",
            "border": 1,
        },
        metric_value_format={"border": 1, "num_format": "#,##0.00"},
        negative_format={"font_color": "#B42318", "bg_color": "#FEE4E2"},
        chart_style=10,
        tab_color="#3578A8",
    ),
    ("excel.operating-review.v1", "1.0.0"): ExcelTemplate(
        code="excel.operating-review.v1",
        version="1.0.0",
        title_format={
            "bold": True,
            "font_size": 16,
            "font_color": "#FFFFFF",
            "bg_color": "#3F4A3C",
            "align": "left",
            "valign": "vcenter",
        },
        header_format={
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#687660",
            "border": 1,
            "align": "center",
        },
        text_format={"border": 1, "font_color": "#20251E"},
        number_format={"border": 1, "num_format": "#,##0.00"},
        integer_format={"border": 1, "num_format": "0"},
        percent_format={"border": 1, "num_format": "0.00%"},
        metric_label_format={
            "bold": True,
            "bg_color": "#E6E9E2",
            "border": 1,
        },
        metric_value_format={"border": 1, "num_format": "#,##0.00"},
        negative_format={"font_color": "#9B2C2C", "bg_color": "#FDE8E7"},
        chart_style=12,
        tab_color="#687660",
    ),
}


def get_excel_template(code: str, version: str) -> ExcelTemplate:
    try:
        return _TEMPLATES[(code, version)]
    except KeyError as exception:
        raise ValueError("excel_template_invalid") from exception
