import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Run the actual TypeScript plugin through the production Markdown parser.
const code = ts.transpileModule(readFileSync(new URL("../lib/citations.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText;
const { remarkCitations, sourceHref } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
const sources = [
  { n: 1, title: "Sleep guide", category: "sleep", url: "https://example.test/sleep.pdf" },
  { n: 2, title: "Care guide", category: "care_options", url: "https://example.test/care.pdf" },
];
const render = (text, refs = sources) => renderToStaticMarkup(React.createElement(ReactMarkdown, {
  remarkPlugins: [remarkGfm, [remarkCitations, { sources: refs }]],
}, text));
const links = (html) => (html.match(/class="citation-link"/g) || []).length;

test("individual, repeated, adjacent and grouped citations link the correct source", () => {
  const html = render("First [1]. Again [1][2]. Together [1, 2] and [2; 1]. Unknown [99].");
  assert.equal(links(html), 7);
  assert.equal((html.match(/href="https:\/\/example.test\/sleep.pdf"/g) || []).length, 4);
  assert.match(html, /aria-label="Source 1: Sleep guide \(opens in a new tab\)"/);
  assert.match(html, /Unknown \[99\]/);
});

test("links work inside lists, emphasis and tables, preserving other Markdown", () => {
  const html = render("- **See [1]**\n\n| Topic | Guide |\n| --- | --- |\n| Care | [2] |");
  assert.equal(links(html), 2);
  assert.match(html, /<strong>/);
  assert.match(html, /<table>/);
});

test("existing links, reference links and code are not rewritten or nested", () => {
  const html = render("`[1]`\n\n```text\n[2]\n```\n\n[[1]](https://example.test/original)\n\n[2][ref]\n\n[ref]: https://example.test/reference");
  assert.equal(links(html), 0);
  assert.match(html, /<code>\[1\]<\/code>/);
  assert.match(html, /href="https:\/\/example.test\/original"/);
  assert.match(html, /href="https:\/\/example.test\/reference"/);
});

test("incomplete streaming markers and old history without metadata remain plain", () => {
  assert.equal(links(render("See [1")), 0);
  assert.equal(links(render("See [1]")), 1);
  assert.equal(links(render("See [1]", [])), 0);
});

test("numbering is scoped to this answer, not the catalogue or previous answer", () => {
  const html = render("See [1]", [{ ...sources[1], n: 1 }]);
  assert.match(html, /href="https:\/\/example.test\/care.pdf"/);
  assert.doesNotMatch(html, /sleep.pdf/);
});

test("unavailable, unsafe or ambiguous sources never create citation links", () => {
  for (const url of [null, "javascript:alert(1)", "data:text/html,test", "//example.test/a", "https://user:secret@example.test", "bad url"]) {
    assert.equal(sourceHref(url), null);
    assert.equal(links(render("See [1]", [{ ...sources[0], url }])), 0);
  }
  assert.equal(links(render("See [1]", [sources[0], { ...sources[1], n: 1 }])), 0);
  assert.equal(links(render("See [1, 99]")), 1);
});
