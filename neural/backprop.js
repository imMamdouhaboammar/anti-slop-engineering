// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadNeuralGraph } from "./router.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, "..");
const ledgerPath = resolve(rootDir, ".anti-slop", "invariant-ledger.json");

/**
 * Backpropagate a test failure or code smell finding into the upstream invariant ledger.
 * @param {object} finding
 * @param {string} finding.type - Finding type or rule identifier
 * @param {string} finding.file - File where failure occurred
 * @param {string} finding.message - Detail message
 * @param {string} [finding.remediation] - Remediation step
 * @returns {object} Backpropagation result
 */
export function backpropagateFinding(finding) {
  if (!finding || !finding.type) {
    throw new Error("Finding with 'type' is required for backpropagation.");
  }

  const graph = loadNeuralGraph();
  const matchedInvariant = graph.invariants.find(
    (inv) =>
      inv.id.toLowerCase().includes(finding.type.toLowerCase()) ||
      finding.type.toLowerCase().includes(inv.guard.toLowerCase())
  );

  let ledger = { invariants: [], invariants_count: 0, schema_version: "1.0.0" };
  if (existsSync(ledgerPath)) {
    try {
      ledger = JSON.parse(readFileSync(ledgerPath, "utf8"));
    } catch {
      // ignore
    }
  }

  const invariantId = matchedInvariant ? matchedInvariant.id : `INV-BACKPROP-${finding.type.toUpperCase()}`;
  let existing = (ledger.invariants || []).find((i) => i.id === invariantId);

  const now = new Date().toISOString();
  if (existing) {
    existing.last_violated_at = now;
    existing.violation_count = (existing.violation_count || 0) + 1;
    existing.last_violation_file = finding.file;
  } else {
    existing = {
      id: invariantId,
      category: matchedInvariant ? matchedInvariant.category : "backpropagated_findings",
      assertion: `Backpropagated invariant from failure: ${finding.message || finding.type}`,
      rationale: `Enforces upstream prevention for downstream issue detected in ${finding.file || "unknown file"}.`,
      enforcement_scope: {
        paths: finding.file ? [finding.file] : ["**/*"],
        patterns: [finding.type],
      },
      status: "active",
      created_at: now,
      violation_count: 1,
    };
    ledger.invariants = ledger.invariants || [];
    ledger.invariants.push(existing);
  }

  ledger.invariants_count = ledger.invariants.length;
  ledger.updated_at = now;

  writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + "\n", "utf8");

  return {
    status: "backpropagated",
    invariant_id: invariantId,
    file: finding.file,
    ledger_path: ledgerPath,
    total_invariants: ledger.invariants_count,
  };
}
