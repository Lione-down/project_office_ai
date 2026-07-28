import DOMPurify, { type Config } from "dompurify";
import MarkdownIt from "markdown-it";


const markdown = new MarkdownIt({
  html: false,
  linkify: false,
  breaks: true,
  typographer: false,
});

markdown.disable(["image"]);
markdown.validateLink = (url) => {
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
};
markdown.renderer.rules.link_open = (tokens, index, options, environment, self) => {
  const token = tokens[index];
  token.attrSet("rel", "noopener noreferrer");
  token.attrSet("target", "_blank");
  return self.renderToken(tokens, index, options);
};

const SANITIZE_OPTIONS: Config = {
  ALLOWED_TAGS: [
    "p",
    "br",
    "strong",
    "em",
    "s",
    "blockquote",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "hr",
  ],
  ALLOWED_ATTR: ["href", "rel", "target"],
  ALLOW_DATA_ATTR: false,
  FORBID_TAGS: [
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "svg",
    "math",
    "img",
  ],
};

export function renderSafeMarkdown(source: string): string {
  return DOMPurify.sanitize(markdown.render(source), SANITIZE_OPTIONS);
}

export function markdownToPlainText(source: string): string {
  const container = document.createElement("div");
  container.innerHTML = renderSafeMarkdown(source);
  return container.textContent?.trim() ?? "";
}
