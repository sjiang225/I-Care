import type { Root, Text, Link } from "mdast";
import type { Parent } from "unist";
import type { Source } from "./api";

/** Only explicit web URLs from this answer's source metadata become links. */
export function sourceHref(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return ["https:", "http:"].includes(parsed.protocol) && !parsed.username && !parsed.password
      ? parsed.href : null;
  } catch { return null; }
}

/** Transform text nodes, never code, existing links, raw HTML or definitions. */
export function remarkCitations({ sources = [] }: { sources?: Source[] } = {}) {
  const byNumber = new Map<number, Source>();
  const seen = new Set<number>();
  for (const source of sources) {
    if (!Number.isSafeInteger(source.n) || source.n < 1) continue;
    if (seen.has(source.n)) { byNumber.delete(source.n); continue; }
    seen.add(source.n);
    if (sourceHref(source.url)) byNumber.set(source.n, source);
  }
  return (tree: Root) => {
    if (!byNumber.size) return;
    function walk(parent: Parent) {
      parent.children = parent.children.flatMap((node) => {
        if (["link", "linkReference", "definition", "code", "inlineCode", "html"].includes(node.type)) return [node];
        if (node.type !== "text") {
          if ("children" in node) walk(node as Parent);
          return [node];
        }
        const text = (node as Text).value;
        const parts: (Text | Link)[] = [];
        let offset = 0;
        for (const match of text.matchAll(/\[(\d+(?:\s*[,;]\s*\d+)*)\]/g)) {
          const numbers = match[1].split(/\s*[,;]\s*/);
          if (!numbers.some((n) => byNumber.has(Number(n)))) continue;
          if (match.index! > offset) parts.push({ type: "text", value: text.slice(offset, match.index) });
          numbers.forEach((number, index) => {
            if (index) parts.push({ type: "text", value: ", " });
            const source = byNumber.get(Number(number));
            if (!source) { parts.push({ type: "text", value: `[${number}]` }); return; }
            parts.push({
              type: "link", url: sourceHref(source.url)!,
              title: `Source ${source.n}: ${source.title} (opens in a new tab)`,
              children: [{ type: "text", value: `[${number}]` }],
              data: { hProperties: {
                className: "citation-link",
                "aria-label": `Source ${source.n}: ${source.title} (opens in a new tab)`,
              } },
            });
          });
          offset = match.index! + match[0].length;
        }
        if (!offset) return [node];
        if (offset < text.length) parts.push({ type: "text", value: text.slice(offset) });
        return parts;
      });
    }
    walk(tree);
  };
}
