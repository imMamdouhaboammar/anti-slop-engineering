// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const graphPath = resolve(__dirname, "graph.json");

let cachedGraph = null;

export function loadNeuralGraph() {
  if (cachedGraph) return cachedGraph;
  if (!existsSync(graphPath)) {
    throw new Error(`Neural graph not found at ${graphPath}`);
  }
  cachedGraph = JSON.parse(readFileSync(graphPath, "utf8"));
  return cachedGraph;
}

/**
 * Route an intent, file path, or code snippet through the neural connection graph.
 * @param {object} query
 * @param {string} [query.intent] - Free text user intent or prompt
 * @param {string[]} [query.files] - List of touched or target file paths
 * @param {string} [query.diff] - Git diff string
 * @returns {object} Activation result with matched invariants, recommended agent, MCP tools, and CLI commands
 */
export function routeNeuralQuery(query = {}) {
  const graph = loadNeuralGraph();
  const textToScan = [
    query.intent || "",
    (query.files || []).join(" "),
    query.diff || "",
  ].join(" ").toLowerCase();

  const activations = [];

  for (const inv of graph.invariants) {
    let weight = 0;
    const tokens = [
      inv.id.toLowerCase(),
      inv.category.toLowerCase(),
      ...inv.description.toLowerCase().split(/\W+/).filter((w) => w.length > 3),
      inv.guard.toLowerCase(),
      inv.skill.toLowerCase(),
    ];

    for (const t of tokens) {
      if (textToScan.includes(t)) {
        weight += 1;
      }
    }

    // Match file extension patterns if provided
    if (query.files && query.files.length > 0) {
      for (const f of query.files) {
        const ext = f.split(".").pop();
        for (const pat of inv.file_patterns) {
          if (pat.includes(`*.${ext}`)) {
            weight += 2;
          }
        }
      }
    }

    if (weight > 0) {
      activations.push({ invariant: inv, weight });
    }
  }

  // Sort activations by weight descending
  activations.sort((a, b) => b.weight - a.weight);

  const topActivations = activations.slice(0, 5);
  const primary = topActivations[0]?.invariant;

  const recommendedAgent = primary ? primary.agent : "anti-slop-orchestrator";
  const recommendedMcpTool = primary ? primary.mcp_tool : "anti_slop_audit";
  const recommendedGuard = primary ? primary.guard : "audit";

  return {
    query,
    total_invariants: graph.invariants.length,
    matched_count: topActivations.length,
    top_invariants: topActivations.map((a) => ({
      id: a.invariant.id,
      category: a.invariant.category,
      description: a.invariant.description,
      weight: a.weight,
    })),
    recommended: {
      agent: recommendedAgent,
      mcp_tool: recommendedMcpTool,
      guard_subsystem: recommendedGuard,
      cli_command: `anti-slop-engineering ${recommendedGuard.replace('_guard', '')}`,
      skill: primary ? primary.skill : "anti-slop-engineering",
    },
  };
}
