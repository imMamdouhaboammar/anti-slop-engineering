import { createRequire } from "node:module";
import path from "node:path";

const [tscJs, workspace, packageName, symbol] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const ts = require(path.join(path.dirname(tscJs), "typescript.js"));
const probePath = path.join(workspace, "__anti_slop_probe__.ts");
const probeText = `import { ${symbol} } from "${packageName}";\nexport type Probe = typeof ${symbol};\n`;
const options = {
  noEmit: true,
  strict: true,
  target: ts.ScriptTarget.ES2020,
  module: ts.ModuleKind.CommonJS,
  moduleResolution: ts.ModuleResolutionKind.NodeJs,
  types: [],
  skipLibCheck: true,
};
const host = ts.createCompilerHost(options);
const readSource = host.getSourceFile.bind(host);
host.getSourceFile = (name, languageVersion, ...rest) => (name === probePath
  ? ts.createSourceFile(name, probeText, languageVersion, true)
  : readSource(name, languageVersion, ...rest));
const program = ts.createProgram([probePath], options, host);
const checker = program.getTypeChecker();
const source = program.getSourceFile(probePath);
const statement = source.statements.find((node) => ts.isImportDeclaration(node));
const moduleSymbol = checker.getSymbolAtLocation(statement.moduleSpecifier);
if (!moduleSymbol) {
  console.log(JSON.stringify({
    compiler_version: ts.version, status: "inconclusive",
    reason: "The selected package could not be resolved from the workspace",
  }));
} else {
  const found = checker.getExportsOfModule(moduleSymbol).find((entry) => entry.name === symbol);
  const declaration = found && (found.declarations || [])[0];
  if (!found) {
    console.log(JSON.stringify({ compiler_version: ts.version, status: "not_declared" }));
  } else if (!declaration) {
    console.log(JSON.stringify({
      compiler_version: ts.version, status: "inconclusive",
      reason: "The exported symbol has no declaration the compiler can locate",
    }));
  } else {
    const file = declaration.getSourceFile();
    const start = file.getLineAndCharacterOfPosition(declaration.getStart());
    const end = file.getLineAndCharacterOfPosition(declaration.getEnd());
    console.log(JSON.stringify({
      compiler_version: ts.version, status: "declared", path: file.fileName,
      line: start.line + 1, column: start.character,
      end_line: end.line + 1, end_column: end.character,
    }));
  }
}
