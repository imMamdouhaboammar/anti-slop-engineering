#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, "..");

function log(msg) {
  console.log(`[anti-slop] ${msg}`);
}

function installSkills() {
  log("Auto-installing agent skill via skills.sh...");
  try {
    const isBun = typeof process.versions.bun !== "undefined";
    const runner = isBun ? "bunx" : "npx";
    const res = spawnSync(
      runner,
      ["skills", "add", "imMamdouhaboammar/anti-slop-engineering", "-y"],
      {
        stdio: "inherit",
        env: process.env,
      }
    );
    if (res.status === 0) {
      log("Agent skill linked into detected AI coding agents.");
    } else {
      log("Tip: Run 'npx skills add imMamdouhaboammar/anti-slop-engineering' to connect manually.");
    }
  } catch (err) {
    log(`Skill auto-install notice: ${err.message}`);
  }
}

function setupMicroservices() {
  const rustDir = resolve(rootDir, "services", "anti-slop-rust");
  const goDir = resolve(rootDir, "services", "toil-guard-go");

  const hasRustSource = existsSync(rustDir);
  const hasGoSource = existsSync(goDir);

  if (!hasRustSource && !hasGoSource) {
    log("Standard library Python 3 diff and SRE engines are active.");
    return;
  }

  const hasCargo = spawnSync("cargo", ["--version"], { stdio: "ignore" }).status === 0;
  const hasGo = spawnSync("go", ["version"], { stdio: "ignore" }).status === 0;

  if (hasCargo && hasGo) {
    log("Native Rust & Go compilers found. Building release binaries...");
    try {
      const cliPath = resolve(__dirname, "cli.js");
      const buildProc = spawnSync("node", [cliPath, "build"], {
        stdio: "inherit",
      });
      if (buildProc.status === 0) {
        log("Native microservices compiled and ready.");
      }
    } catch {
      log("Native compilation skipped. Python engines ready.");
    }
  } else {
    log("Zero-dependency Python 3 engines ready. Run 'anti-slop-engineering build' anytime to compile native microservices.");
  }
}

// Execute postinstall sequence
installSkills();
setupMicroservices();
process.exit(0);
