// Regenerates the eleven illustrated-guide screenshots in public/help/.
//
// Usage (frontend and backend running locally, guest session):
//   npm i --no-save playwright-core
//   node scripts/capture-help-screens.cjs [http://localhost:3000]
//
// Every image is the same 390 x 360 CSS-pixel window of the phone layout,
// captured at 2x for sharp display, with the control to use outlined in red.
// Chat is intercepted with a synthetic reply; library and questionnaire reads
// are real, and no assessment is submitted. The signed-in view is simulated by
// intercepting the auth and history calls, so no account is created.
const path = require("path");
const { chromium } = require("playwright-core");

const BASE = process.argv[2] || "http://localhost:3000";
const OUT = path.join(__dirname, "..", "public", "help");
const VIEWPORT = { width: 390, height: 844 };
const FRAME_HEIGHT = 360;

(async () => {
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 2 });
  await page.goto(`${BASE}/#home`);
  await page.addStyleTag({ content: `
    .help-shot-target { outline: 3px solid #cc0033 !important; outline-offset: 3px; border-radius: 10px; }
    * { caret-color: transparent !important; }
    nextjs-portal { display: none !important; }` });

  // Outline the targets, centre them in the frame, and capture a fixed-size window.
  async function shot(name, ...targets) {
    await targets[0].evaluate((el) => el.scrollIntoView({ block: "center" }));
    const boxes = [];
    for (const [index, target] of targets.entries()) {
      if (index === 0 || name === "library") await target.evaluate((el) => el.classList.add("help-shot-target"));
      boxes.push(await target.boundingBox());
    }
    const top = Math.min(...boxes.map((b) => b.y));
    const bottom = Math.max(...boxes.map((b) => b.y + b.height));
    const y = Math.max(0, Math.min(Math.round((top + bottom) / 2 - FRAME_HEIGHT / 2), VIEWPORT.height - FRAME_HEIGHT));
    await page.screenshot({ path: path.join(OUT, `${name}.png`), animations: "disabled",
      clip: { x: 0, y, width: VIEWPORT.width, height: FRAME_HEIGHT } });
    for (const target of targets) await target.evaluate((el) => el.classList.remove("help-shot-target"));
  }

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await shot("start", page.locator(".home-primary"), page.locator("#home-heading"));
  await shot("home", nav.getByRole("button", { name: "Home", exact: true }));
  await shot("signin", page.locator(".signin-btn"));
  await page.locator(".signin-btn").click();
  await page.locator(".auth-card").waitFor();
  await shot("signin-form", page.locator(".auth-form"), page.locator(".auth-head h2"));
  await page.getByRole("button", { name: "Close", exact: true }).click();

  await nav.getByRole("button", { name: "Chat", exact: true }).click();
  await page.getByRole("textbox", { name: "Your question or message" }).fill("Where can I find information about sleep?");
  await shot("question", page.locator(".composer"));

  const catalogue = await (await page.request.get(`${BASE}/api/library`)).json();
  const guide = catalogue.documents.find((item) => item.category === "sleep");
  const video = catalogue.videos.find((item) => item.category === "sleep");
  const event = (kind, data) => `event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`;
  await page.route("**/api/chat", (route) => route.fulfill({ contentType: "text/event-stream", body:
    event("sources", { sources: [{ ...guide, n: 1 }] }) +
    event("resources", { helplines: [], facilities: [], facilities_note: "", videos: [video] }) +
    event("delta", { text: "Here are some ideas for calmer nights, from a Care2Caregivers guide. [1]" }) +
    event("done", {}) }));
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.locator(".citation-link").waitFor();
  await page.waitForTimeout(300);
  await shot("reply", page.locator(".turn.assistant .col").last());

  await nav.getByRole("button", { name: "Library", exact: true }).click();
  await page.getByRole("group", { name: "Resource type" }).waitFor();
  await shot("library", page.locator(".library-types"), page.locator(".library-filters"));
  await page.getByRole("button", { name: /^Videos/ }).click();
  await page.getByRole("searchbox", { name: "Search resources" }).fill("sleep");
  await page.locator(".guide-link").first().waitFor();
  await shot("resource", page.locator(".guide-link").first());

  await nav.getByRole("button", { name: "Self-assessment", exact: true }).click();
  await page.locator(".sa-instrument").first().waitFor();
  await shot("assessment", page.locator(".sa-instrument").first());
  await page.getByRole("button", { name: /GAD-7/ }).click();
  await page.locator(".sa-question").first().waitFor();
  await shot("answer", page.locator(".sa-question").first());

  // Simulated signed-in session for the Sign out step.
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: { id: 1, email: "caregiver@example.com", display_name: "Alex" } }));
  await page.route("**/api/history", (route) => route.fulfill({ json: { latest_conversation_id: null, latest_messages: [] } }));
  await page.evaluate(() => { localStorage.setItem("icare_token", "help-guide-example"); location.hash = "#home"; });
  await page.reload();
  await page.addStyleTag({ content: `
    .help-shot-target { outline: 3px solid #cc0033 !important; outline-offset: 3px; border-radius: 10px; }
    nextjs-portal { display: none !important; }` });
  await page.getByRole("button", { name: /^Sign out/ }).waitFor();
  await shot("signout", page.getByRole("button", { name: /^Sign out/ }));
  await page.evaluate(() => localStorage.removeItem("icare_token"));

  await browser.close();
  console.log(`Captured 11 screenshots into ${OUT}`);
})().catch((error) => { console.error(error); process.exit(1); });
