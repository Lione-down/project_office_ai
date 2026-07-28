import { describe, expect, it } from "vitest";

import { renderSafeMarkdown } from "./safe-markdown";


describe("safe chat Markdown", () => {
  it("renders basic Markdown but removes raw HTML and dangerous URLs", () => {
    const rendered = renderSafeMarkdown(
      [
        "## 标题",
        "<script>alert(1)</script>",
        '<img src=x onerror="alert(2)">',
        "[危险链接](javascript:alert(3))",
        "[文件](file:///private.txt)",
        "[安全链接](https://example.com/reference)",
        "![跟踪图](https://tracker.invalid/pixel.png)",
      ].join("\n"),
    );

    expect(rendered).toContain("<h2");
    expect(rendered).not.toContain("<script");
    expect(rendered).not.toMatch(/<[^>]+\sonerror=/u);
    expect(rendered).not.toContain('href="javascript:');
    expect(rendered).not.toContain('href="file:');
    expect(rendered).not.toContain("<img");
    expect(rendered).toContain('href="https://example.com/reference"');
    expect(rendered).toContain('rel="noopener noreferrer"');
  });
});
