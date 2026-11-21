#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const RULES_PATH = path.join(__dirname, '..', 'rules', 'AGENTS.md');
const ROOT_RULES_PATH = path.join(__dirname, '..', 'AGENTS.md');

export function getFallbackInstructions() {
  return `ANTI-SLOP ENGINEERING ACTIVE — 7 Gates & SRE Invariants Engaged

1. Gate 0 Preflight & Invariant Inversion: Infer domain intent autonomously; name tools briefly; never edit blindly.
2. The Google SRE Mandate:
   - KISS: Nesting <= 4, function length <= 80 lines.
   - DRY: Single source of truth. Deduplicate >= 4 lines.
   - YAGNI: No speculative arguments, dead branches, or placeholder TODOs.
   - Toil Elimination: Exponential backoff with full jitter; bounded concurrency; no silent error swallowing.
3. Clean-Room Dev Ladder & SHIT Interceptors:
   - Intercept Scope creep, Hypothetical hardening, Intent violation, Task thrashing.
   - Standard library built-ins first (crypto.randomUUID, structuredClone, URLSearchParams).
4. Type-Level & AST Slop Gate:
   - Eliminate chained assertions (as unknown as T) and ungrounded casts without // SAFETY:.
   - Eliminate quadratic reducer copies and conditional empty spreads.
5. Zero-Obviousness & Comment Budget: CCR <= 0.35. Ban syntax play-by-play comments.
6. Apple Craft, Interaction Physics & WCAG 2.2 Contrast:
   - Exhaustive UI states; CLS = 0.000; interruptible compositor-driven physics; contrast >= 4.5:1.
7. Zero-Trust & Active Battlefield Scale:
   - Boundary schema parsing; distributed idempotency; constant-time crypto; RFC 9457 error contracts.
8. Mandela Test-Oracle Integrity:
   - Zero tautological assertions, zero circular mock verifications, zero swallowed assertions.
9. NVIDIA Re0 Context Reset & Cold-Read Shower Test:
   - State notes <= 1,500 tokens with OBJECTIVE, PROVEN_INVARIANTS, NEGATIVE_CORPUS, NEXT_SINGLE_ACTION.
`;
}

export function getAntiSlopInstructions() {
  const candidates = [RULES_PATH, ROOT_RULES_PATH];
  for (const candidate of candidates) {
    try {
      const content = fs.readFileSync(candidate, 'utf8').trim();
      return `ANTI-SLOP ENGINEERING ACTIVE — 7 Gates & SRE Invariants Engaged\n\n${content}`;
    } catch (err) {
      if (err && err.code === 'ENOENT') {
        continue;
      }
    }
  }
  return getFallbackInstructions();
}
