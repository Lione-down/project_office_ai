import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";

import {
  type ChartDataSource,
  type ChartElement,
  type PresentationElement,
  type PresentationPlan,
  type PresentationSlide,
  type TableDataSource,
  parsePresentationPlan,
} from "./contracts.js";
import {
  createPresentation,
  type PresentationApi,
  type SlideApi,
} from "./pptx-api.js";
import {
  defineTemplateMasters,
  masterName,
  templateFor,
  type SystemTemplate,
} from "./templates.js";

export interface RenderResult {
  outputPath: string;
  sha256: string;
  byteSize: number;
  slideCount: number;
  templateCode: string;
  templateVersion: string;
  rendererVersion: string;
}

export async function renderPresentation(
  input: unknown,
  outputPath: string,
): Promise<RenderResult> {
  const plan = parsePresentationPlan(input);
  const template = templateFor(plan.template);
  const pptx = buildPresentation(plan, template);

  await pptx.writeFile({ fileName: outputPath, compression: true });
  const [bytes, details] = await Promise.all([readFile(outputPath), stat(outputPath)]);
  return {
    outputPath,
    sha256: createHash("sha256").update(bytes).digest("hex"),
    byteSize: details.size,
    slideCount: plan.slides.length,
    templateCode: plan.template.code,
    templateVersion: plan.template.version,
    rendererVersion: plan.renderer_version,
  };
}

function buildPresentation(
  plan: PresentationPlan,
  template: SystemTemplate,
): PresentationApi {
  const pptx = createPresentation();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = plan.metadata.author;
  pptx.company = plan.metadata.company;
  pptx.subject = plan.metadata.subject;
  pptx.title = plan.metadata.title;
  pptx.revision = plan.metadata.revision;
  pptx.theme = {
    headFontFace: template.headFontFace,
    bodyFontFace: template.bodyFontFace,
  };
  defineTemplateMasters(pptx, template);

  for (const slidePlan of plan.slides) {
    const slide = pptx.addSlide({
      masterName: masterName(template.code, slidePlan.layout),
    });
    renderSlideTitle(slide, slidePlan, template);
    for (const element of slidePlan.elements) {
      renderElement(pptx, slide, plan, element, template);
    }
    slide.addNotes(
      [...slidePlan.speaker_notes, evidenceNote(slidePlan)].filter(Boolean).join("\n"),
    );
  }
  return pptx;
}

function renderSlideTitle(
  slide: SlideApi,
  plan: PresentationSlide,
  template: SystemTemplate,
): void {
  const centered = plan.layout !== "content";
  slide.addText(plan.title, {
    placeholder: "slide-title",
    x: centered ? 1.0 : 0.8,
    y: centered ? 1.8 : 0.35,
    w: centered ? 11.33 : 11.75,
    h: centered ? 1.4 : 0.65,
    fontFace: template.headFontFace,
    fontSize: centered ? 30 : 24,
    bold: true,
    color: template.primary,
    align: centered ? "center" : "left",
    valign: "middle",
    margin: 0,
  });
  if (plan.subtitle) {
    slide.addText(plan.subtitle, {
      x: 1.3,
      y: 3.35,
      w: 10.73,
      h: 0.65,
      fontFace: template.bodyFontFace,
      fontSize: 18,
      color: template.muted,
      align: "center",
      margin: 0,
    });
  }
}

function renderElement(
  pptx: PresentationApi,
  slide: SlideApi,
  plan: PresentationPlan,
  element: PresentationElement,
  template: SystemTemplate,
): void {
  const position = { x: element.x, y: element.y, w: element.w, h: element.h };
  if (element.type === "text") {
    slide.addText(element.text, {
      ...position,
      fontFace: template.bodyFontFace,
      fontSize: 18,
      color: template.text,
      margin: 4,
      valign: "top",
      fit: "shrink",
    });
    return;
  }
  if (element.type === "source") {
    slide.addText(element.text, {
      ...position,
      fontFace: template.bodyFontFace,
      fontSize: 8,
      color: template.muted,
      margin: 0,
      fit: "shrink",
    });
    return;
  }
  if (element.type === "image") {
    const image = plan.images[element.image_id];
    if (!image) throw new Error("presentation_data_reference_invalid");
    slide.addImage({
      data: image.data_uri,
      altText: image.alt_text,
      ...position,
      sizing: { type: "contain", ...position },
    });
    return;
  }
  const source = plan.data_sources[element.data_source_id];
  if (element.type === "table") {
    renderTable(slide, source as TableDataSource, element, template);
    return;
  }
  renderChart(pptx, slide, source as ChartDataSource, element, template);
}

function renderTable(
  slide: SlideApi,
  source: TableDataSource,
  element: Extract<PresentationElement, { type: "table" }>,
  template: SystemTemplate,
): void {
  const fontSize =
    source.columns.length > 6 ? 8 : source.rows.length > 8 ? 9 : 11;
  const rows = [
    source.columns.map((text) => ({
      text,
      options: {
        bold: true,
        color: "FFFFFF",
        fill: { color: template.primary },
      },
    })),
    ...source.rows.map((row, rowIndex) =>
      row.map((value, columnIndex) => ({
        text: String(value),
        options: {
          bold: columnIndex === 0,
          fill: { color: rowIndex % 2 === 0 ? template.surface : template.background },
        },
      })),
    ),
  ];
  slide.addTable(rows, {
    x: element.x,
    y: element.y,
    w: element.w,
    h: element.h,
    fontFace: template.bodyFontFace,
    fontSize,
    color: template.text,
    border: { type: "solid", color: "D8DEE8", pt: 0.5 },
    fill: { color: template.surface },
    margin: 3,
    autoFit: false,
  });
}

function renderChart(
  pptx: PresentationApi,
  slide: SlideApi,
  source: ChartDataSource,
  element: ChartElement,
  template: SystemTemplate,
): void {
  const chartType = pptx.ChartType[element.chart_type];
  slide.addChart(
    chartType,
    source.series.map((series) => ({
      name: series.name,
      labels: source.categories,
      values: series.values,
    })),
    {
      x: element.x,
      y: element.y,
      w: element.w,
      h: element.h,
      showLegend: source.series.length > 1 || element.chart_type === "pie",
      legendPos: "b",
      showTitle: false,
      showValue: element.chart_type === "pie",
      showPercent: element.chart_type === "pie",
      chartColors: [template.primary, template.secondary, template.accent],
      catAxisLabelFontFace: template.bodyFontFace,
      catAxisLabelFontSize: 10,
      valAxisLabelFontFace: template.bodyFontFace,
      valAxisLabelFontSize: 10,
      legendFontFace: template.bodyFontFace,
      legendFontSize: 9,
      showCatName: false,
      showSerName: false,
      showBorder: false,
    },
  );
  return;
}

function evidenceNote(slide: PresentationSlide): string {
  const evidenceIds = [
    ...new Set(
      slide.elements.flatMap((element) =>
        "evidence_ids" in element && element.evidence_ids
          ? element.evidence_ids
          : [],
      ),
    ),
  ];
  return evidenceIds.length ? `Evidence: ${evidenceIds.join(", ")}` : "";
}
