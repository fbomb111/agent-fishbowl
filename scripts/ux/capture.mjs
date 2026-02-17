#!/usr/bin/env node
/**
 * Capture screenshots of the Agent Fishbowl frontend for UX review.
 *
 * Usage:
 *   node capture.mjs [--url URL] [--output-dir DIR] [--routes ROUTE1,ROUTE2]
 *
 * Defaults:
 *   --url         https://agentfishbowl.com
 *   --output-dir  /tmp/ux-screenshots
 *   --routes      /,/activity,/blog,/feedback,/goals
 */
import { chromium } from "playwright";
import { mkdir } from "fs/promises";
import { join } from "path";

// --- CLI arg parsing ---
function parseArgs(argv) {
  const args = {
    url: "https://agentfishbowl.com",
    outputDir: "/tmp/ux-screenshots",
    routes: ["/", "/activity", "/blog", "/feedback", "/goals"],
  };

  for (let i = 2; i < argv.length; i++) {
    switch (argv[i]) {
      case "--url":
        args.url = argv[++i];
        break;
      case "--output-dir":
        args.outputDir = argv[++i];
        break;
      case "--routes":
        args.routes = argv[++i].split(",").map((r) => r.trim());
        break;
    }
  }
  return args;
}

// --- Viewports ---
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
];

// --- Route to filename ---
function routeToName(route) {
  if (route === "/") return "home";
  return route.replace(/^\//, "").replace(/\//g, "-");
}

// --- Main ---
async function main() {
  const args = parseArgs(process.argv);
  await mkdir(args.outputDir, { recursive: true });

  const captured = [];
  const errors = [];

  const browser = await chromium.launch({ headless: true });

  try {
    for (const viewport of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        deviceScaleFactor: viewport.name === "mobile" ? 2 : 1,
      });
      const page = await context.newPage();

      for (const route of args.routes) {
        const name = routeToName(route);
        const filename = `${name}-${viewport.name}.png`;
        const filepath = join(args.outputDir, filename);
        const url = `${args.url.replace(/\/$/, "")}${route}`;

        try {
          await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
          // Wait a beat for any animations/transitions to settle
          await page.waitForTimeout(1000);
          await page.screenshot({ path: filepath, fullPage: true });
          captured.push({ route, viewport: viewport.name, file: filepath });
        } catch (err) {
          errors.push({
            route,
            viewport: viewport.name,
            error: err.message,
          });
        }
      }

      await context.close();
    }
  } finally {
    await browser.close();
  }

  // Output JSON summary
  const result = {
    url: args.url,
    output_dir: args.outputDir,
    captured,
    errors,
    total: captured.length,
  };

  console.log(JSON.stringify(result, null, 2));

  if (errors.length > 0) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error("Fatal error:", err.message);
  process.exit(2);
});
