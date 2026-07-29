import { createHash } from "node:crypto";

export const ONE_PIXEL_PNG =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
const onePixelBytes = Buffer.from(ONE_PIXEL_PNG.split(",", 2)[1], "base64");

export const samplePlan = {
  schema_version: "presentation-plan.v1",
  renderer_version: "ppt-renderer.v1",
  template: {
    code: "ppt.executive-blue.v1",
    version: "1.0.0",
  },
  locale: "zh-CN",
  metadata: {
    title: "2026 上半年销售经营汇报",
    subject: "脱敏 synthetic renderer contract sample",
    author: "Office AI",
    company: "Office AI",
    revision: "1",
  },
  evidence_ids: ["ev-revenue", "ev-region", "ev-product", "ev-risk"],
  images: {
    "hero-image": {
      asset_id: "019fad40-0000-7000-8000-000000000001",
      asset_version: 1,
      data_uri: ONE_PIXEL_PNG,
      mime_type: "image/png",
      byte_size: onePixelBytes.length,
      sha256: createHash("sha256").update(onePixelBytes).digest("hex"),
      width: 1,
      height: 1,
      crop_mode: "contain",
      alt_text: "脱敏示例图片",
    },
  },
  data_sources: {
    "regional-sales": {
      kind: "chart",
      categories: ["华东", "华南", "华北"],
      series: [
        { name: "销售额", values: [120, 98, 76] },
        { name: "目标", values: [110, 100, 80] },
      ],
    },
    "monthly-trend": {
      kind: "chart",
      categories: ["1月", "2月", "3月", "4月"],
      series: [{ name: "销售额", values: [80, 92, 101, 115] }],
    },
    "product-mix": {
      kind: "chart",
      categories: ["产品A", "产品B", "其他"],
      series: [{ name: "占比", values: [52, 31, 17] }],
    },
    "key-metrics": {
      kind: "table",
      columns: ["指标", "本期", "同比"],
      rows: [
        ["销售额", "294 万元", "+12.4%"],
        ["毛利率", "38.2%", "+1.8pp"],
      ],
    },
  },
  slides: [
    {
      layout: "title",
      title: "2026 上半年销售经营汇报",
      subtitle: "经营结果、区域表现与下一步行动",
      speaker_notes: ["本页用于说明汇报范围。"],
      elements: [
        {
          type: "image",
          image_id: "hero-image",
          decorative: true,
          x: 9.6,
          y: 1.5,
          w: 2.6,
          h: 2.6,
        },
      ],
    },
    {
      layout: "content",
      title: "核心经营指标",
      speaker_notes: ["强调销售额和毛利率变化。"],
      elements: [
        {
          type: "text",
          text: "销售额同比增长 12.4%，毛利率提升 1.8 个百分点。",
          evidence_ids: ["ev-revenue"],
          x: 0.8,
          y: 1.35,
          w: 5.7,
          h: 0.8,
        },
        {
          type: "table",
          data_source_id: "key-metrics",
          evidence_ids: ["ev-revenue"],
          x: 0.8,
          y: 2.25,
          w: 5.7,
          h: 2.2,
        },
        {
          type: "chart",
          chart_type: "bar",
          data_source_id: "regional-sales",
          evidence_ids: ["ev-region"],
          x: 6.8,
          y: 1.35,
          w: 5.7,
          h: 3.8,
        },
        {
          type: "source",
          text: "来源：脱敏 synthetic sales dataset",
          evidence_ids: ["ev-revenue", "ev-region"],
          x: 0.8,
          y: 6.72,
          w: 11.7,
          h: 0.28,
        },
      ],
    },
    {
      layout: "content",
      title: "趋势与产品结构",
      speaker_notes: ["趋势图与产品结构均来自已确认 Evidence。"],
      elements: [
        {
          type: "chart",
          chart_type: "line",
          data_source_id: "monthly-trend",
          evidence_ids: ["ev-revenue"],
          x: 0.8,
          y: 1.35,
          w: 5.7,
          h: 4.4,
        },
        {
          type: "chart",
          chart_type: "pie",
          data_source_id: "product-mix",
          evidence_ids: ["ev-product"],
          x: 6.8,
          y: 1.35,
          w: 5.7,
          h: 4.4,
        },
        {
          type: "source",
          text: "来源：ev-revenue、ev-product",
          evidence_ids: ["ev-revenue", "ev-product"],
          x: 0.8,
          y: 6.72,
          w: 11.7,
          h: 0.28,
        },
      ],
    },
    {
      layout: "closing",
      title: "下一步行动",
      speaker_notes: ["确认行动负责人和复盘节奏。"],
      elements: [
        {
          type: "text",
          text: "聚焦高潜区域、优化产品组合、每月复盘关键风险。",
          evidence_ids: ["ev-risk"],
          x: 1.2,
          y: 2.2,
          w: 10.9,
          h: 1.2,
        },
        {
          type: "source",
          text: "依据：ev-risk",
          evidence_ids: ["ev-risk"],
          x: 1.2,
          y: 5.9,
          w: 10.9,
          h: 0.3,
        },
      ],
    },
  ],
} as const;

export function clonePlan(): Record<string, unknown> {
  return structuredClone(samplePlan) as unknown as Record<string, unknown>;
}
