/**
 * Example: Using Stagehand (TypeScript) with Observius reporting.
 *
 * Prerequisites:
 *   npm install stagehand @anthropic-ai/sdk
 *   Observius running: make dev
 */
import { Stagehand } from "stagehand";
import { ObserviusReporter } from "./observius-reporter";

async function main() {
  const reporter = new ObserviusReporter({
    apiUrl: process.env.OBSERVIUS_API_URL || "http://localhost:8000",
    apiKey: process.env.OBSERVIUS_API_KEY || "cu_test_testkey1234567890abcdef12",
  });

  const stagehand = new Stagehand({ env: "LOCAL" });
  await stagehand.init();

  reporter.start("Extract company info from example.com");

  try {
    await stagehand.page.goto("https://example.com");
    reporter.recordStep({
      actionType: "navigate",
      description: "Opened example.com",
    });

    const data = await stagehand.extract({
      instruction: "get the main heading text",
      schema: { heading: { type: "string" } },
    });
    reporter.recordStep({
      actionType: "extract",
      description: `Extracted heading: ${data.heading}`,
    });

    const taskId = await reporter.complete();
    console.log(`View in dashboard: http://localhost:3000/tasks/${taskId}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await reporter.fail(message);
    console.error("Task failed:", message);
  } finally {
    await stagehand.close();
  }
}

main();
