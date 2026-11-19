import { createGameExperienceMemory } from "./game-experience-memory.mjs";

const [id, feedback] = process.argv.slice(2);
if (!id || !["good", "bad"].includes(feedback)) {
  console.error("Usage: npm run feedback -- <experience-id> <good|bad>");
  process.exitCode = 2;
} else {
  try {
    const memory = createGameExperienceMemory({
      filePath: process.env.AUTOEARN_MEMORY_FILE || ".autoearn/experience-memory.json"
    });
    const result = await memory.rate(id, feedback);
    console.log("Saved owner feedback:", JSON.stringify(result));
  } catch (error) {
    console.error(error.message || error);
    process.exitCode = 1;
  }
}
