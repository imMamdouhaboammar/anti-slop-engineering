import { defineRule } from "@oxlint/plugins";

import { resolveVariable } from "../shared/scope.ts";

import type { ESTree, SourceCode } from "@oxlint/plugins";

function matchesReactImport(
  sourceCode: SourceCode,
  identifier: ESTree.Expression,
  memberAccess: boolean,
): boolean {
  if (identifier.type !== "Identifier") return false;
  const binding = resolveVariable(sourceCode, identifier);
  if (binding?.defs.length !== 1) return false;

  const definition = binding.defs[0];
  if (definition.type !== "ImportBinding" || definition.parent.type !== "ImportDeclaration" ||
      definition.parent.source.value !== "react" || definition.parent.importKind === "type") return false;

  const specifier = definition.node;
  if (specifier.type === "ImportSpecifier") {
    if (specifier.importKind === "type") return false;
    const imported = specifier.imported;
    const name = imported.type === "Identifier" ? imported.name : imported.value;
    return name === (memberAccess ? "default" : "forwardRef");
  }

  return memberAccess && (specifier.type === "ImportDefaultSpecifier" || specifier.type === "ImportNamespaceSpecifier");
}

export const reactForwardRefEvidenceRule = defineRule({
  meta: {
    type: "suggestion",
    docs: { description: "Locate calls to the React forwardRef import around inline function components." },
    messages: {
      reactWrapper: "React forwardRef wraps an inline function component. Verify the locked React release and the supported versions before proposing a ref-prop migration.",
    },
  },
  createOnce(context) {
    return {
      CallExpression(node) {
        const component = node.arguments[0];
        if (node.optional || node.arguments.length !== 1 ||
            (component?.type !== "FunctionExpression" && component?.type !== "ArrowFunctionExpression")) return;
        const callee = node.callee;
        if (callee.type === "Identifier" && matchesReactImport(context.sourceCode, callee, false)) {
          context.report({ node, messageId: "reactWrapper" });
        } else if (callee.type === "MemberExpression" && !callee.optional &&
            (callee.computed ? callee.property.type === "Literal" && callee.property.value === "forwardRef"
              : callee.property.type === "Identifier" && callee.property.name === "forwardRef") &&
            matchesReactImport(context.sourceCode, callee.object, true)) {
          context.report({ node, messageId: "reactWrapper" });
        }
      },
    };
  },
});
