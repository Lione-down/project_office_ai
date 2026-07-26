from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = REPOSITORY_ROOT / "docs" / "ALPHA_RELEASE.md"


def _read_release_report() -> str:
    assert REPORT_PATH.is_file(), "T4-005 requires docs/ALPHA_RELEASE.md"
    return REPORT_PATH.read_text(encoding="utf-8")


def test_release_report_has_all_hard_gate_sections() -> None:
    report = _read_release_report()

    required_sections = (
        "## 封版结论",
        "## 可重复验证",
        "## Docker 冷启动与 Readiness",
        "## MySQL 空库迁移",
        "## Agnes 与黄金回归",
        "## Microsoft Office 与 WPS",
        "## Git 与敏感信息 Gate",
        "## Alpha 完成定义",
        "## 已声明边界",
    )

    for section in required_sections:
        assert section in report, f"missing release evidence section: {section}"


def test_release_report_covers_every_stable_suite_and_runtime_gate() -> None:
    report = _read_release_report()

    required_evidence = (
        "Backend full",
        "Backend integration",
        "Frontend test",
        "Frontend build",
        "PPT Renderer test",
        "PPT Renderer build",
        "Golden regression",
        "/health/ready",
        "base -> head",
        "alembic check",
        "真实 Agnes Contract",
        "Microsoft Office",
        "WPS Office",
        "退出码 `0`",
    )

    for evidence in required_evidence:
        assert evidence in report, f"missing release evidence: {evidence}"


def test_release_report_preserves_pilot_and_security_boundaries() -> None:
    report = _read_release_report()

    required_boundaries = (
        "`1/10 pilot`",
        "不能证明原计划 10 组 corpus 的多样性",
        "tracked files",
        "staged paths",
        "新增历史",
        "`.env`",
        "Secret",
        "用户文件",
        "未脱敏材料",
        "总计划第 23 节",
    )

    for boundary in required_boundaries:
        assert boundary in report, f"missing release boundary: {boundary}"
