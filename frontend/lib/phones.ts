import type { Root, Text, Link, PhrasingContent } from "mdast";
import type { Parent } from "unist";

// North American numbers such as 1-800-424-2494, 800.424.2494 or (877) 222-3737.
const PHONE = /(?<![\w.-])(?:\+?1[-.\s])?(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.\s]\d{4}(?![\w-])/g;
// 911 and 988 only when an action word precedes them, so other numbers stay text.
const SHORT = /\b(call|text|dial)((?:\s+or\s+(?:call|text))?)\s+(911|988)\b/gi;
const SHORT_BEFORE = /\b(call|text|dial)(?:\s+or\s+(?:call|text))?\s*$/i;
const SKIP = ["link", "linkReference", "definition", "code", "inlineCode", "html"];

/** True only for the dial links this plugin creates (digits, optional leading +). */
export function isPhoneHref(url: string): boolean {
  return /^(tel:\+?\d{3,15}|sms:\d{3,15})$/.test(url);
}

/** tel:/sms: href for a displayed number; "text 988" alone opens messaging. */
export function phoneHref(display: string, verb = "call"): string {
  const digits = display.replace(/\D/g, "");
  if (digits.length <= 3) return `${verb.toLowerCase() === "text" ? "sms" : "tel"}:${digits}`;
  return `tel:+${digits.length === 10 ? "1" + digits : digits}`;
}

function phoneLink(display: string, href: string): Link {
  const action = href.startsWith("sms:") ? "Text" : "Call";
  return {
    type: "link", url: href, children: [{ type: "text", value: display }],
    data: { hProperties: { className: "phone-link", "aria-label": `${action} ${display}` } },
  };
}

function splitText(text: string): PhrasingContent[] {
  const found: { start: number; end: number; node: Link }[] = [];
  for (const m of text.matchAll(PHONE)) {
    found.push({ start: m.index!, end: m.index! + m[0].length, node: phoneLink(m[0], phoneHref(m[0])) });
  }
  for (const m of text.matchAll(SHORT)) {
    const start = m.index! + m[0].length - m[3].length;
    const verb = m[2] ? "call" : m[1];
    found.push({ start, end: start + m[3].length, node: phoneLink(m[3], phoneHref(m[3], verb)) });
  }
  if (!found.length) return [{ type: "text", value: text }];
  found.sort((a, b) => a.start - b.start);
  const parts: PhrasingContent[] = [];
  let offset = 0;
  for (const { start, end, node } of found) {
    if (start < offset) continue;
    if (start > offset) parts.push({ type: "text", value: text.slice(offset, start) });
    parts.push(node);
    offset = end;
  }
  if (offset < text.length) parts.push({ type: "text", value: text.slice(offset) });
  return parts;
}

/** Make phone numbers in assistant replies tappable; never touches code or existing links. */
export function remarkPhoneLinks() {
  return (tree: Root) => {
    function walk(parent: Parent) {
      const out: Parent["children"] = [];
      parent.children.forEach((node, index) => {
        if (SKIP.includes(node.type)) { out.push(node); return; }
        // "call **911**": the number sits alone inside bold/italic after the action word.
        const previous = parent.children[index - 1];
        if ((node.type === "strong" || node.type === "emphasis") && previous?.type === "text") {
          const children = (node as Parent).children;
          const only = children.length === 1 && children[0].type === "text" ? (children[0] as Text).value.trim() : "";
          const verb = (previous as Text).value.match(SHORT_BEFORE);
          if ((only === "911" || only === "988") && verb) {
            const href = phoneHref(only, /or/i.test(verb[0]) ? "call" : verb[1]);
            (node as Parent).children = [phoneLink(only, href)];
            out.push(node);
            return;
          }
        }
        if (node.type === "text") { out.push(...splitText((node as Text).value)); return; }
        if ("children" in node) walk(node as Parent);
        out.push(node);
      });
      parent.children = out;
    }
    walk(tree);
  };
}
