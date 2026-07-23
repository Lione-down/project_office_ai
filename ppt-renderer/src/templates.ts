import type { PresentationTemplateRef } from "./contracts.js";
import type { PresentationApi } from "./pptx-api.js";

type TemplateCode = PresentationTemplateRef["code"];
type LayoutName = "title" | "content" | "section" | "closing";

export interface SystemTemplate {
  code: TemplateCode;
  version: "1.0.0";
  name: string;
  background: string;
  surface: string;
  primary: string;
  secondary: string;
  accent: string;
  text: string;
  muted: string;
  headFontFace: string;
  bodyFontFace: string;
}

export const SYSTEM_TEMPLATES: readonly SystemTemplate[] = [
  {
    code: "ppt.executive-blue.v1",
    version: "1.0.0",
    name: "Executive Blue",
    background: "F5F8FC",
    surface: "FFFFFF",
    primary: "123B6D",
    secondary: "2F6FB0",
    accent: "29A3A3",
    text: "172033",
    muted: "64748B",
    headFontFace: "Microsoft YaHei",
    bodyFontFace: "Microsoft YaHei",
  },
  {
    code: "ppt.operating-review.v1",
    version: "1.0.0",
    name: "Operating Review",
    background: "F8F7F3",
    surface: "FFFFFF",
    primary: "24443A",
    secondary: "49766A",
    accent: "D08B45",
    text: "1F2A27",
    muted: "6D7D77",
    headFontFace: "Microsoft YaHei",
    bodyFontFace: "Microsoft YaHei",
  },
  {
    code: "ppt.data-story.v1",
    version: "1.0.0",
    name: "Data Story",
    background: "F8F6FC",
    surface: "FFFFFF",
    primary: "3D2C68",
    secondary: "7357A8",
    accent: "DD6B7B",
    text: "251F32",
    muted: "746B84",
    headFontFace: "Microsoft YaHei",
    bodyFontFace: "Microsoft YaHei",
  },
] as const;

export function templateFor(reference: PresentationTemplateRef): SystemTemplate {
  const template = SYSTEM_TEMPLATES.find(
    (candidate) =>
      candidate.code === reference.code && candidate.version === reference.version,
  );
  if (!template) {
    throw new Error("presentation_template_invalid");
  }
  return template;
}

export function masterName(code: TemplateCode, layout: LayoutName): string {
  return `${code}:${layout}`;
}

export function defineTemplateMasters(
  pptx: PresentationApi,
  template: SystemTemplate,
): void {
  for (const layout of ["title", "content", "section", "closing"] as const) {
    const isCentered = layout !== "content";
    const titleBox = isCentered
      ? { x: 1.0, y: 1.8, w: 11.33, h: 1.4 }
      : { x: 0.8, y: 0.35, w: 11.75, h: 0.65 };
    pptx.defineSlideMaster({
      title: masterName(template.code, layout),
      background: { color: template.background },
      objects: [
        {
          rect: {
            x: 0,
            y: 0,
            w: 13.333,
            h: isCentered ? 0.18 : 0.12,
            line: { color: template.primary, transparency: 100 },
            fill: { color: template.primary },
          },
        },
        {
          placeholder: {
            text: "",
            options: {
              name: "slide-title",
              type: "title",
              ...titleBox,
              fontFace: template.headFontFace,
              fontSize: isCentered ? 30 : 24,
              bold: true,
              color: template.primary,
              align: isCentered ? "center" : "left",
              margin: 0,
            },
          },
        },
        {
          placeholder: {
            text: "",
            options: {
              name: "slide-body",
              type: "body",
              x: 0.8,
              y: 1.25,
              w: 11.75,
              h: 5.7,
              fontFace: template.bodyFontFace,
              fontSize: 18,
              color: template.text,
              margin: 0,
            },
          },
        },
        {
          text: {
            text: `${template.name} · Office AI`,
            options: {
              x: 0.8,
              y: 7.12,
              w: 4.2,
              h: 0.2,
              fontFace: template.bodyFontFace,
              fontSize: 8,
              color: template.muted,
              margin: 0,
            },
          },
        },
      ],
      slideNumber: {
        x: 12.15,
        y: 7.08,
        w: 0.45,
        h: 0.24,
        fontFace: template.bodyFontFace,
        fontSize: 9,
        color: template.muted,
        align: "right",
        margin: 0,
      },
    });
  }
}
