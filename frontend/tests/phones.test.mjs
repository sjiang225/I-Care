import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

// Run the actual TypeScript plugin through the production Markdown parser.
const code = ts.transpileModule(readFileSync(new URL("../lib/phones.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText;
const { remarkPhoneLinks, phoneHref, isPhoneHref } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
const render = (text) => renderToStaticMarkup(React.createElement(ReactMarkdown, {
  remarkPlugins: [remarkGfm, remarkPhoneLinks],
  urlTransform: (url) => (isPhoneHref(url) ? url : defaultUrlTransform(url)),
}, text));
const hrefs = (html) => [...html.matchAll(/href="([^"]+)"/g)].map((m) => m[1]);

test("common helpline formats in reply text become tel links", () => {
  const html = render("Call the helpline at 1-800-424-2494, 800.424.2494 or the ADRC at 877-222-3737. Also (732) 235-4886.");
  assert.deepEqual(hrefs(html), ["tel:+18004242494", "tel:+18004242494", "tel:+18772223737", "tel:+17322354886"]);
  assert.match(html, /aria-label="Call 1-800-424-2494"/);
  assert.match(html, />877-222-3737</);
});

test("911 and 988 link only after call/text/dial, including bold safety notices", () => {
  const html = render("Please call **911** right away. Call or text **988** (24/7). You can text 988 too.");
  assert.deepEqual(hrefs(html), ["tel:911", "tel:988", "sms:988"]);
  assert.match(html, /<strong><a[^>]*href="tel:911"[^>]*>911<\/a><\/strong>/);
});

test("other numbers, code and existing links are left alone", () => {
  const html = render("In 1988, about 988 people and 911 cases. Code `800-424-2494`. [site](https://example.test/800-424-2494). ZIP 08901, year 2026.");
  assert.deepEqual(hrefs(html), ["https://example.test/800-424-2494"]);
  assert.match(html, /<code>800-424-2494<\/code>/);
});

test("only plain dial links pass the URL filter", () => {
  assert.ok(isPhoneHref("tel:+18004242494") && isPhoneHref("tel:911") && isPhoneHref("sms:988"));
  assert.ok(!isPhoneHref("tel:911;javascript:alert(1)") && !isPhoneHref("javascript:alert(1)"));
  const html = render("[x](javascript:alert(1)) and [y](tel:abc)");
  assert.ok(!/javascript:|tel:abc/.test(html));
});

test("phoneHref normalises display formats", () => {
  assert.equal(phoneHref("1-800-424-2494"), "tel:+18004242494");
  assert.equal(phoneHref("800.424.2494"), "tel:+18004242494");
  assert.equal(phoneHref("988"), "tel:988");
  assert.equal(phoneHref("988", "text"), "sms:988");
});
