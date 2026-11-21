// anti-slop-engineering — Pi & Oh My Pi (omp) extension.
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { getAntiSlopInstructions } = require("../hooks/anti-slop-instructions.js");

export default function activate(pi) {
  if (!pi || typeof pi.on !== "function") return;

  pi.on("session_start", async (_event, ctx) => {
    if (ctx?.ui?.notify) {
      ctx.ui.notify("Anti-Slop Engineering active: 7 gates & SRE guards engaged", "info");
    }
  });

  pi.on("before_agent_start", async (event) => {
    const instructions = getAntiSlopInstructions();
    const sections = event?.systemPromptOptions?.sections;
    if (sections && typeof sections === "object") {
      sections.anti_slop = instructions;
      return;
    }
    if (Array.isArray(event?.systemPrompt)) {
      return { systemPrompt: [...event.systemPrompt, instructions] };
    }
    const base = event?.systemPrompt ? `${event.systemPrompt}\n\n` : "";
    return { systemPrompt: `${base}${instructions}` };
  });
}
