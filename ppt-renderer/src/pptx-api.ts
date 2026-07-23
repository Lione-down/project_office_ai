import PptxGenJSImport from "pptxgenjs";

export interface SlideApi {
  addText(text: string, options: Record<string, unknown>): void;
  addImage(options: Record<string, unknown>): void;
  addTable(rows: unknown[], options: Record<string, unknown>): void;
  addChart(
    chartType: string,
    data: unknown[],
    options: Record<string, unknown>,
  ): void;
  addNotes(notes: string): void;
}

export interface PresentationApi {
  layout: string;
  author: string;
  company: string;
  subject: string;
  title: string;
  revision: string;
  theme: { headFontFace?: string; bodyFontFace?: string };
  ChartType: Record<"bar" | "line" | "pie", string>;
  defineSlideMaster(properties: Record<string, unknown>): void;
  addSlide(properties: { masterName: string }): SlideApi;
  writeFile(properties: {
    fileName: string;
    compression?: boolean;
  }): Promise<string>;
}

const PptxConstructor = PptxGenJSImport as unknown as new () => PresentationApi;

export function createPresentation(): PresentationApi {
  return new PptxConstructor();
}
