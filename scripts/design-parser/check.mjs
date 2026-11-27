// Parse candidate text only; never import, evaluate, or build candidate modules.
import ts from "typescript";
import * as css from "css-tree";
import { parse } from "parse5";

const fail = code => { throw new Error(code); };
const check = (condition, code) => { if (!condition) fail(code); };
const TOKEN = "UI_UNAPPROVED_TOKEN";
const STYLE = "UI_STYLE_UNVERIFIED";
const PARSE = "UI_SOURCE_PARSE_FAILED";
const NEUTRAL = new Set(["0", "auto", "none", "transparent", "currentcolor", "inherit", "initial", "unset", "revert", "revert-layer"]);
const DESIGN = /^(?:color|background(?:-.+)?|.+-color|fill|stroke|border(?:-.+)?|outline(?:-.+)?|(?:margin|padding)(?:-.+)?|(?:row-|column-)?gap|font(?:-.+)?|line-height|letter-spacing|.+-radius|box-shadow|text-shadow|filter|backdrop-filter|(?:min-|max-)?(?:width|height|inline-size|block-size)|transform(?:-origin)?|translate|rotate|scale)$/i;
const COLOR = /^(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix|light-dark|(?:repeating-)?(?:linear|radial|conic)-gradient)$/i;
const SINK = new Set(["style", "classList", "className", "innerHTML", "outerHTML", "insertAdjacentHTML",
  "insertRule", "replaceSync", "adoptedStyleSheets", "createElement", "createElementNS",
  "setAttribute", "setAttributeNS", "cssText", "dangerouslySetInnerHTML", "srcDoc"]);
const ATTR = new Set(["className", "class", "style", "data-design-component", "dangerouslySetInnerHTML", "srcDoc"]);
const AT_RULES = new Set(["media", "supports", "layer", "container", "keyframes", "-webkit-keyframes", "starting-style"]);

function parseCSS(source, context = "stylesheet") {
  return css.parse(source, { context, parseCustomProperty: true, onParseError: () => fail(PARSE) });
}

function variable(node, tokens) {
  const children = node.children.toArray();
  check(children.length === 1 && children[0].type === "Identifier", TOKEN);
  const name = css.ident.decode(children[0].name);
  check(Object.hasOwn(tokens, name), TOKEN);
}

function tokenOnly(value, tokens, property = "") {
  const parts = value.children.toArray();
  check(parts.length > 0, TOKEN);
  for (const part of parts) {
    if (part.type === "Function" && css.ident.decode(part.name).toLowerCase() === "var") {
      variable(part, tokens);
      continue;
    }
    if (/^(?:min-|max-)?(?:width|height|inline-size|block-size)$/i.test(property) &&
        ((part.type === "Percentage" && ["0", "100"].includes(part.value)) ||
         (part.type === "Identifier" && ["min-content", "max-content", "fit-content", "stretch"].includes(part.name)))) continue;
    check((part.type === "Number" && Number(part.value) === 0) ||
          (part.type === "Identifier" && NEUTRAL.has(css.ident.decode(part.name).toLowerCase())), TOKEN);
  }
}

function checkValue(value, tokens) {
  css.walk(value, node => {
    check(node.type !== "Raw", PARSE);
    check(node.type !== "Hash", TOKEN);
    check(node.type !== "Url", STYLE);
    if (node.type !== "Function") return;
    const name = css.ident.decode(node.name).toLowerCase();
    if (name === "var") variable(node, tokens);
    else check(!COLOR.test(name) && name !== "url" && name !== "image-set", TOKEN);
  });
}

function checkDeclaration(node, tokens) {
  const property = css.ident.decode(node.property);
  if (property.startsWith("--")) {
    check(Object.hasOwn(tokens, property) &&
      css.generate(node.value) === css.generate(parseCSS(tokens[property], "value")) && !node.important, TOKEN);
    return;
  }
  checkValue(node.value, tokens);
  if (DESIGN.test(property)) tokenOnly(node.value, tokens, property);
}

function checkCSS(source, tokens) {
  const ast = parseCSS(source);
  css.walk(ast, node => {
    check(node.type !== "Raw", PARSE);
    if (node.type === "Atrule") check(AT_RULES.has(css.ident.decode(node.name).toLowerCase()), STYLE);
    if (node.type === "Declaration") checkDeclaration(node, tokens);
  });
}

function checkClass(value, policy) {
  const allowed = new Set(policy.allowed_classes);
  check(value.split(/\s+/u).filter(Boolean).every(item => allowed.has(item)), "UI_UNAPPROVED_UTILITY");
}

function checkAttribute(name, values, manifest, policy) {
  if (name === "class" || name === "className") {
    values.forEach(value => checkClass(value, policy));
  } else if (name === "data-design-component") {
    check(values.every(value => manifest.components.includes(value)), "UI_UNAPPROVED_COMPONENT");
  } else if (ATTR.has(name)) {
    fail(STYLE);
  } else if (DESIGN.test(name)) {
    values.forEach(value => tokenOnly(parseCSS(value, "value"), manifest.tokens));
  }
}

function staticStrings(node) {
  if (!node) fail(STYLE);
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return [node.text];
  if (ts.isParenthesizedExpression(node)) return staticStrings(node.expression);
  if (ts.isConditionalExpression(node)) return [...staticStrings(node.whenTrue), ...staticStrings(node.whenFalse)];
  fail(STYLE);
}

function jsxAttribute(node, manifest, policy) {
  check(!ts.isJsxSpreadAttribute(node), STYLE);
  const raw = node.name.getText();
  const name = raw.toLowerCase() === "style" ? "style" : raw;
  if (!ATTR.has(name) && !DESIGN.test(name)) return;
  if (name === "style" || name === "dangerouslySetInnerHTML" || name === "srcDoc") fail(STYLE);
  const init = node.initializer;
  const value = init && ts.isJsxExpression(init) ? init.expression : init;
  checkAttribute(name, staticStrings(value), manifest, policy);
}

function jsxTag(node, manifest, policy) {
  const tag = node.tagName.getText();
  if (/^[A-Z]/.test(tag) || tag.includes(".") || tag.includes("-") || tag.includes(":")) {
    check(manifest.components.includes(tag), "UI_UNAPPROVED_COMPONENT");
  }
  check(!["style", "script", "iframe", "object", "embed", "svg", "link", "base"].includes(tag.toLowerCase()), STYLE);
  node.attributes.properties.forEach(attr => jsxAttribute(attr, manifest, policy));
}

function constantString(node) {
  if (!node) return null;
  if (ts.isStringLiteralLike(node)) return node.text;
  if (ts.isParenthesizedExpression(node)) return constantString(node.expression);
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    const left = constantString(node.left), right = constantString(node.right);
    if (left !== null && right !== null) return left + right;
  }
  return null;
}

function propertyName(node) {
  if (ts.isPropertyAccessExpression(node)) return node.name.text;
  if (ts.isElementAccessExpression(node)) return constantString(node.argumentExpression);
  return null;
}

function declaredProperty(node) {
  if (ts.isComputedPropertyName(node)) return constantString(node.expression);
  return node.text;
}

function checkJS(source, name, manifest, policy) {
  const ast = ts.createSourceFile(name, source, ts.ScriptTarget.Latest, true);
  check(ast.parseDiagnostics.length === 0, PARSE);
  function visit(node) {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) jsxTag(node, manifest, policy);
    const prop = propertyName(node);
    if (prop) check(!SINK.has(prop), STYLE);
    if (ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node)) {
      check(!SINK.has(declaredProperty(node.name)), STYLE);
    }
    if (ts.isBindingElement(node) && ts.isObjectBindingPattern(node.parent)) {
      check(!SINK.has(declaredProperty(node.propertyName ?? node.name)), STYLE);
    }
    ts.forEachChild(node, visit);
  }
  visit(ast);
}

function localResource(value) {
  return value && value === value.trim() && !/[\x00-\x20\x7f]/u.test(value) &&
    !/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(value) && !value.includes("\\");
}

function checkHTML(source, manifest, policy) {
  const ast = parse(source, { onParseError: error => {
    if (error.code !== "missing-doctype") fail(PARSE);
  }});
  function visit(node) {
    const attrs = Object.fromEntries((node.attrs ?? []).map(attr => [attr.name, attr.value]));
    for (const [name, value] of Object.entries(attrs)) {
      check(!name.startsWith("on") && name !== "srcdoc", STYLE);
      checkAttribute(name, [value], manifest, policy);
    }
    if (node.tagName === "style") checkCSS(node.childNodes.map(child => child.value ?? "").join(""), manifest.tokens);
    if (node.tagName === "script") {
      check(localResource(attrs.src) && !node.childNodes.some(child => child.value?.trim()), STYLE);
    }
    if (node.tagName === "link" && attrs.rel?.toLowerCase().split(/\s+/).includes("stylesheet")) check(localResource(attrs.href), STYLE);
    check(!["iframe", "object", "embed", "base", "svg"].includes(node.tagName), STYLE);
    if (node.tagName?.includes("-")) check(manifest.components.includes(node.tagName), "UI_UNAPPROVED_COMPONENT");
    for (const child of node.childNodes ?? []) visit(child);
    if (node.content) visit(node.content);
  }
  visit(ast);
}

function scan({name, source, manifest, policy}) {
  if (name.toLowerCase().endsWith(".css")) return checkCSS(source, manifest.tokens);
  if (/\.(?:html|htm)$/i.test(name)) return checkHTML(source, manifest, policy);
  if (/\.(?:[cm]?[jt]s|[jt]sx)$/i.test(name)) return checkJS(source, name, manifest, policy);
  fail("UI_IMPACT_UNKNOWN");
}

try {
  scan(JSON.parse(await Bun.stdin.text()));
  console.log(JSON.stringify({ok: true}));
} catch (error) {
  const code = /^UI_[A-Z_]+$/.test(error.message) ? error.message : PARSE;
  console.log(JSON.stringify({ok: false, code}));
}
