import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { reviewForwardRef, reviewLegacyRender } from "../skills/type-level-and-ast-slop-gate/examples/react-ref-advisory.mjs";

const evidence = { status: "locked", resolved: "19.0.0", release: "stable" };
const usage = { module: "react", export: "forwardRef", kind: "function-component" };
const compatibility = ["19.0.0", "19.1.0"];

test("React 19 function component wrapper receives an advisory with migration evidence", () => {
  const result = reviewForwardRef(evidence, usage, compatibility);
  assert.equal(result.status, "advisory");
  assert.equal(result.severity, "review");
  assert.equal(result.version, "19.0.0");
  assert.match(result.source, /^https:\/\/react\.dev\//);
  assert.match(result.suggestion, /ref prop/);
});

test("React 18, prereleases and unverified lock evidence do not trigger advice", () => {
  assert.equal(reviewForwardRef({ ...evidence, resolved: "18.3.1" }, usage, compatibility).status, "not_applicable");
  assert.equal(reviewForwardRef({ ...evidence, resolved: "19.0.0-rc.1", release: "prerelease" }, usage, compatibility).status, "inconclusive");
  assert.equal(reviewForwardRef({ ...evidence, status: "stale_lock" }, usage, compatibility).status, "inconclusive");
  assert.equal(reviewForwardRef({ ...evidence, resolved: "19malformed" }, usage, compatibility).status, "inconclusive");
});

test("keep wrappers for React 18 consumers and require declared support evidence", () => {
  assert.equal(reviewForwardRef(evidence, usage, ["18.3.1", "19.0.0"]).status, "compatibility_exception");
  assert.equal(reviewForwardRef(evidence, usage, []).status, "inconclusive");
  assert.equal(reviewForwardRef(evidence, usage, ["19.x"]).status, "inconclusive");
  assert.equal(reviewForwardRef(evidence, { ...usage, module: "preact/compat" }, compatibility).status, "not_applicable");
  assert.equal(reviewForwardRef(evidence, { ...usage, kind: "class-component" }, compatibility).status, "not_applicable");
});

test("CLI consumes a lock-evidence receipt and a reviewed usage record without blocking", (context) => {
  const dir = mkdtempSync(join(tmpdir(), "react-ref-evidence-"));
  context.after(() => rmSync(dir, { recursive: true, force: true }));
  const lock = join(dir, "lock.json");
  const example = join(dir, "usage.json");
  writeFileSync(lock, JSON.stringify(evidence));
  writeFileSync(example, JSON.stringify({ ...usage, supportedVersions: compatibility }));
  const script = new URL("../skills/type-level-and-ast-slop-gate/examples/react-ref-advisory.mjs", import.meta.url);
  const output = Bun.spawnSync([process.execPath, script.pathname, lock, example]);
  assert.equal(output.exitCode, 0);
  assert.equal(JSON.parse(output.stdout.toString()).status, "advisory");
});

test("later majors and malformed release receipts remain inconclusive", () => {
  assert.equal(reviewForwardRef({ ...evidence, resolved: "20.0.0" }, usage, ["20.0.0"]).status, "inconclusive");
  assert.equal(reviewForwardRef(evidence, usage, ["19.0.0", "20.0.0"]).status, "inconclusive");
  assert.equal(reviewForwardRef(null, usage, compatibility).status, "inconclusive");
  assert.equal(reviewForwardRef(evidence, { ...usage, export: "memo" }, compatibility).status, "not_applicable");
});


const domEvidence = {
  status: "locked", resolved: "19.0.0", release: "stable",
  installed: { status: "installed", name: "react-dom", version: "19.0.0" },
};
const renderUsage = { module: "react-dom", export: "render", kind: "call" };

test("React DOM 19 legacy render receives an advisory with installed-version evidence", () => {
  const result = reviewLegacyRender(domEvidence, renderUsage, compatibility);
  assert.equal(result.status, "advisory");
  assert.equal(result.severity, "review");
  assert.equal(result.rule, "REACT19_REACT_DOM_RENDER_REMOVED");
  assert.equal(result.version, "19.0.0");
  assert.equal(result.resolved, "19.0.0");
  assert.equal(result.evidence_source, "installed");
  assert.match(result.source, /^https:\/\/react\.dev\/blog\/2024\/04\/25\/react-19-upgrade-guide#removed-reactdomrender$/);
  assert.match(result.suggestion, /createRoot/);
  assert.match(result.suggestion, /react-dom\/client/);
});

test("React DOM 18 and missing installed evidence never trigger render advice", () => {
  const eighteen = {
    status: "locked", resolved: "18.3.1", release: "stable",
    installed: { status: "installed", name: "react-dom", version: "18.3.1" },
  };
  assert.equal(reviewLegacyRender(eighteen, renderUsage, ["18.3.1"]).status, "not_applicable");
  const { installed: _installed, ...noInstalled } = domEvidence;
  assert.equal(reviewLegacyRender(noInstalled, renderUsage, compatibility).status, "inconclusive");
  assert.equal(reviewLegacyRender({ ...domEvidence, installed: { status: "missing" } }, renderUsage, compatibility).status, "inconclusive");
  assert.equal(reviewLegacyRender({ ...domEvidence, installed: { status: "installed", name: "react", version: "19.0.0" } }, renderUsage, compatibility).status, "inconclusive");
  assert.equal(reviewLegacyRender({ ...domEvidence, installed: { status: "installed", name: "react-dom", version: "19.0.0-rc.1" } }, renderUsage, compatibility).status, "inconclusive");
});

test("conflicting render evidence stays inconclusive or a compatibility exception", () => {
  assert.equal(reviewLegacyRender(domEvidence, renderUsage, ["18.3.1", "19.0.0"]).status, "compatibility_exception");
  assert.equal(reviewLegacyRender(domEvidence, renderUsage, []).status, "inconclusive");
  assert.equal(reviewLegacyRender({ ...domEvidence, resolved: "18.3.1" }, renderUsage, compatibility).status, "inconclusive");
  assert.equal(reviewLegacyRender({ ...domEvidence, installed: { ...domEvidence.installed, version: "18.3.1" } }, renderUsage, compatibility).status, "inconclusive");
  assert.equal(reviewLegacyRender({ ...domEvidence, resolved: "20.0.0", installed: { ...domEvidence.installed, version: "18.3.1" } }, renderUsage, compatibility).status, "inconclusive");
  assert.equal(reviewLegacyRender({ ...domEvidence, resolved: "20.0.0" }, renderUsage, compatibility).status, "inconclusive");
  assert.equal(reviewLegacyRender({ ...domEvidence, installed: { status: "installed", name: "react-dom", version: "20.0.0" }, resolved: "20.0.0" }, renderUsage, ["20.0.0"]).status, "inconclusive");
  assert.equal(reviewLegacyRender(domEvidence, { ...renderUsage, module: "react-dom/client" }, compatibility).status, "not_applicable");
  assert.equal(reviewLegacyRender(domEvidence, { ...renderUsage, export: "createRoot" }, compatibility).status, "not_applicable");
  assert.equal(reviewLegacyRender(domEvidence, { ...renderUsage, kind: "function-component" }, compatibility).status, "not_applicable");
});

test("CLI dispatches a React DOM receipt and render usage record to the render advisory", (context) => {
  const dir = mkdtempSync(join(tmpdir(), "react-dom-evidence-"));
  context.after(() => rmSync(dir, { recursive: true, force: true }));
  const lock = join(dir, "lock.json");
  const example = join(dir, "usage.json");
  writeFileSync(lock, JSON.stringify(domEvidence));
  writeFileSync(example, JSON.stringify({ ...renderUsage, supportedVersions: compatibility }));
  const script = new URL("../skills/type-level-and-ast-slop-gate/examples/react-ref-advisory.mjs", import.meta.url);
  const output = Bun.spawnSync([process.execPath, script.pathname, lock, example]);
  assert.equal(output.exitCode, 0);
  const result = JSON.parse(output.stdout.toString());
  assert.equal(result.status, "advisory");
  assert.equal(result.rule, "REACT19_REACT_DOM_RENDER_REMOVED");
});

test("Oxlint resolves genuine React wrappers and leaves shadowed or ambiguous uses alone", (context) => {
  const dir = mkdtempSync(join(tmpdir(), "react-ref-ast-"));
  context.after(() => rmSync(dir, { recursive: true, force: true }));
  const plugin = fileURLToPath(new URL(
    "../skills/install-anti-slop/assets/anti-slop/index.ts", import.meta.url,
  ));
  const oxlint = fileURLToPath(new URL("../node_modules/.bin/oxlint", import.meta.url));
  writeFileSync(join(dir, "oxlint.json"), JSON.stringify({
    jsPlugins: [{ name: "anti-slop", specifier: plugin }],
    categories: { correctness: "off" },
    rules: { "anti-slop/react-forward-ref-evidence": "warn" },
  }));
  writeFileSync(join(dir, "sample.tsx"), [
    'import React, { forwardRef as bridge } from "react";',
    'import * as ReactModule from "react";',
    'import { forwardRef as compat } from "preact/compat";',
    'const named = bridge((props, ref) => <input ref={ref} />);',
    'const namespace = ReactModule.forwardRef(function Input(props, ref) { return <input ref={ref} />; });',
    'const defaultImport = React["forwardRef"]((props, ref) => <input ref={ref} />);',
    'function shadow(bridge, React) {',
    '  bridge((props, ref) => <div />);',
    '  return React.forwardRef((props, ref) => <div />);',
    '}',
    'const otherModule = compat((props, ref) => <div />);',
    'const unresolved = bridge(Component);',
    'const notACall = "React.forwardRef((props, ref) => null)";',
  ].join("\n"));
  const output = Bun.spawnSync([oxlint, "-c", "oxlint.json", "--format=json", "sample.tsx"], { cwd: dir });
  assert.equal(output.exitCode, 0, output.stderr.toString());
  const diagnostics = JSON.parse(output.stdout.toString()).diagnostics;
  const observations = diagnostics.map((finding) => finding.labels[0].span.line).sort((a, b) => a - b);
  assert.deepEqual(observations, [4, 5, 6]);
  for (const finding of diagnostics) {
    assert.equal(finding.code, "anti-slop(react-forward-ref-evidence)");
    assert.equal(finding.severity, "warning");
  }
  const receipt = join(dir, "react-lock.json");
  const support = join(dir, "support.json");
  const report = join(dir, "source-report.json");
  writeFileSync(receipt, JSON.stringify(evidence));
  writeFileSync(support, JSON.stringify({ supportedVersions: compatibility }));
  writeFileSync(report, output.stdout);
  const advisory = fileURLToPath(new URL(
    "../skills/type-level-and-ast-slop-gate/examples/react-ref-advisory.mjs", import.meta.url,
  ));
  const run = () => Bun.spawnSync([process.execPath, advisory, receipt, support, "--oxlint-report", report]);
  let result = run();
  assert.equal(result.exitCode, 0, result.stderr.toString());
  assert.equal(JSON.parse(result.stdout.toString()).status, "advisory");

  writeFileSync(support, JSON.stringify({ supportedVersions: ["18.3.1", "19.0.0"] }));
  result = run();
  assert.equal(result.exitCode, 0, result.stderr.toString());
  assert.equal(JSON.parse(result.stdout.toString()).status, "compatibility_exception");

  writeFileSync(report, JSON.stringify({ diagnostics: [{ code: "unrelated(react-forward-ref-evidence)" }] }));
  result = run();
  assert.equal(result.exitCode, 0, result.stderr.toString());
  assert.equal(JSON.parse(result.stdout.toString()).status, "not_applicable");

});

test("Oxlint resolves genuine React DOM render calls and leaves shadowed or client uses alone", (context) => {
  const dir = mkdtempSync(join(tmpdir(), "react-dom-ast-"));
  context.after(() => rmSync(dir, { recursive: true, force: true }));
  const plugin = fileURLToPath(new URL(
    "../skills/install-anti-slop/assets/anti-slop/index.ts", import.meta.url,
  ));
  const oxlint = fileURLToPath(new URL("../node_modules/.bin/oxlint", import.meta.url));
  writeFileSync(join(dir, "oxlint.json"), JSON.stringify({
    jsPlugins: [{ name: "anti-slop", specifier: plugin }],
    categories: { correctness: "off" },
    rules: { "anti-slop/react-dom-render-evidence": "warn" },
  }));
  writeFileSync(join(dir, "sample.tsx"), [
    'import { render } from "react-dom";',
    'import { render as legacyRender } from "react-dom";',
    'import * as ReactDOM from "react-dom";',
    'import ReactDOMDefault from "react-dom";',
    'import { createRoot } from "react-dom/client";',
    'import { render as otherRender } from "other-dom";',
    'render(<App />, document.body);',
    'legacyRender(<App />, document.body);',
    'ReactDOM.render(<App />, document.body);',
    'ReactDOMDefault.render(<App />, document.body);',
    'createRoot(document.body).render(<App />);',
    'otherRender(<App />, document.body);',
    'function shadow(render) { render(<App />, document.body); }',
    'const referenceOnly = render;',
  ].join("\n"));
  const output = Bun.spawnSync([oxlint, "-c", "oxlint.json", "--format=json", "sample.tsx"], { cwd: dir });
  assert.equal(output.exitCode, 0, output.stderr.toString());
  const diagnostics = JSON.parse(output.stdout.toString()).diagnostics;
  const observations = diagnostics.map((finding) => finding.labels[0].span.line).sort((a, b) => a - b);
  assert.deepEqual(observations, [7, 8, 9, 10]);
  for (const finding of diagnostics) {
    assert.equal(finding.code, "anti-slop(react-dom-render-evidence)");
    assert.equal(finding.severity, "warning");
  }
  const receipt = join(dir, "react-dom-lock.json");
  const support = join(dir, "support.json");
  const report = join(dir, "source-report.json");
  writeFileSync(receipt, JSON.stringify(domEvidence));
  writeFileSync(support, JSON.stringify({ supportedVersions: compatibility }));
  writeFileSync(report, output.stdout);
  const advisory = fileURLToPath(new URL(
    "../skills/type-level-and-ast-slop-gate/examples/react-ref-advisory.mjs", import.meta.url,
  ));
  const run = () => Bun.spawnSync([process.execPath, advisory, receipt, support, "--oxlint-report", report]);
  let result = run();
  assert.equal(result.exitCode, 0, result.stderr.toString());
  const advisoryResult = JSON.parse(result.stdout.toString());
  assert.equal(advisoryResult.status, "advisory");
  assert.equal(advisoryResult.rule, "REACT19_REACT_DOM_RENDER_REMOVED");

  writeFileSync(report, JSON.stringify({
    diagnostics: [{ code: "anti-slop(react-forward-ref-evidence)" }, ...diagnostics],
  }));
  result = run();
  assert.equal(result.exitCode, 0, result.stderr.toString());
  assert.equal(JSON.parse(result.stdout.toString()).rule, "REACT19_REACT_DOM_RENDER_REMOVED");


  writeFileSync(report, JSON.stringify({ diagnostics: [{ code: "anti-slop(react-forward-ref-evidence)" }] }));
  result = run();
  assert.equal(result.exitCode, 0, result.stderr.toString());
  assert.equal(JSON.parse(result.stdout.toString()).status, "not_applicable");

  writeFileSync(report, JSON.stringify({ diagnostics: [{ code: "unrelated(react-dom-render-evidence)" }] }));
  result = run();
  assert.equal(result.exitCode, 0, result.stderr.toString());
  assert.equal(JSON.parse(result.stdout.toString()).status, "not_applicable");
});
