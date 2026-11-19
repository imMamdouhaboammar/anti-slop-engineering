import { defineRule } from "@oxlint/plugins";

import { resolveVariable } from "../shared/scope.ts";

import type { ESTree, SourceCode } from "@oxlint/plugins";

function matchesReactDomImport(
  sourceCode: SourceCode,
  identifier: ESTree.Expression,
  memberAccess: boolean,
): boolean {
  if (identifier.type !== "Identifier") return false;
  const binding = resolveVariable(sourceCode, identifier);
  if (binding?.defs.length !== 1) return false;

  const definition = binding.defs[0];
  if (definition.type !== "ImportBinding" || definition.parent.type !== "ImportDeclaration" ||
      definition.parent.source.value !== "react-dom" || definition.parent.importKind === "type") return false;

  const specifier = definition.node;
  if (specifier.type === "ImportSpecifier") {
    if (specifier.importKind === "type") return false;
    const imported = specifier.imported;
    const name = imported.type === "Identifier" ? imported.name : imported.value;
    return name === (memberAccess ? "default" : "render");
  }

  return memberAccess && (specifier.type === "ImportDefaultSpecifier" || specifier.type === "ImportNamespaceSpecifier");
}

export const reactDomRenderEvidenceRule = defineRule({
  meta: {
    type: "suggestion",
    docs: { description: "Locate calls to the React DOM legacy render import removed in React DOM 19." },
    messages: {
      legacyRender: "React DOM legacy render call. Verify the installed React DOM release and the supported versions before proposing a createRoot migration.",
    },
  },
  createOnce(context) {
    return {
      CallExpression(node) {
        if (node.optional) return;
        const callee = node.callee;
        if (callee.type === "Identifier" && matchesReactDomImport(context.sourceCode, callee, false)) {
          context.report({ node, messageId: "legacyRender" });
        } else if (callee.type === "MemberExpression" && !callee.optional &&
            (callee.computed ? callee.property.type === "Literal" && callee.property.value === "render"
              : callee.property.type === "Identifier" && callee.property.name === "render") &&
            matchesReactDomImport(context.sourceCode, callee.object, true)) {
          context.report({ node, messageId: "legacyRender" });
        }
      },
    };
  },
});
