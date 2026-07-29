const LOCAL_PREVIEW_PATTERN =
  /^\/template-previews\/ppt\.[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*\.v1\/(?:cover|representative)\.svg$/;

export function safeTemplatePreviewUrl(value: string): string {
  return LOCAL_PREVIEW_PATTERN.test(value) ? value : "";
}

export function compatibleTemplateOptions<
  T extends { compatible_skills: string[] },
>(templates: T[], skillCode: string): T[] {
  return templates.filter((template) =>
    template.compatible_skills.includes(skillCode),
  );
}
