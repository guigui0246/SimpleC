import * as path from "path";
import * as vscode from "vscode";
import { spawn } from "child_process";
import * as fs from "fs/promises";

type SimpleCConfig = {
  pythonPath: string;
  runtimeMode: "bundled" | "workspace" | "custom";
  workspaceCliPath: string;
  customCliPath: string;
  additionalArgs: string[];
};

type RunResult = {
  exitCode: number;
  stdout: string;
  stderr: string;
};

type ParserDiagnostic = {
  message: string;
  line: number;
  column: number;
};

type FunctionInfo = {
  name: string;
  params: string[];
  returnType: string;
  signature: string;
  comment?: string;
  nameRange: vscode.Range;
  uri: vscode.Uri;
};

type ParserCheckResult = {
  ok: boolean;
  error?: ParserDiagnostic;
  message?: string;
};

const SIMPLEC_SELECTOR: vscode.DocumentSelector = [
  { language: "simplec", scheme: "file" },
  { language: "simplec", scheme: "untitled" },
];

const SIMPLEC_KEYWORDS = new Set([
  "if",
  "elif",
  "else",
  "while",
  "for",
  "fun",
  "return",
  "print",
  "try",
  "catch",
  "and",
  "or",
  "xor",
  "not",
]);

const UNKNOWN_FUNCTION_DIAG_CODE = "unknown-function";
const WRONG_ARGUMENT_COUNT_DIAG_CODE = "wrong-argument-count";
const MISSING_SEMICOLON_DIAG_CODE = "missing-semicolon";
const UNCLOSED_BRACE_DIAG_CODE = "unclosed-brace";
const UNCLOSED_PAREN_DIAG_CODE = "unclosed-parenthesis";

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel("SimpleC");
  const diagnostics = vscode.languages.createDiagnosticCollection("simplec");
  const functionIndex = new Map<string, FunctionInfo[]>();
  let workspaceFunctionCache: FunctionInfo[] = [];
  const pendingValidationTimers = new Map<string, NodeJS.Timeout>();
  let stdlibFunctionNames = new Set<string>();

  void loadStdlibFunctionNames(context).then((names) => {
    stdlibFunctionNames = names;
  });

  const hoverProvider = vscode.languages.registerHoverProvider(SIMPLEC_SELECTOR, {
    provideHover(document, position) {
      const symbolRange = document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/);
      if (!symbolRange) {
        return undefined;
      }

      const symbol = document.getText(symbolRange);
      const match = findFunctionByName(document.uri, symbol, workspaceFunctionCache);
      if (!match) {
        return undefined;
      }

      const lines: string[] = [`### ${match.name}`, `\`fun ${match.signature}\``];
      if (match.comment) {
        lines.push("", match.comment);
      }

      return new vscode.Hover(new vscode.MarkdownString(lines.join("\n"), true), symbolRange);
    }
  });

  const signatureProvider = vscode.languages.registerSignatureHelpProvider(
    SIMPLEC_SELECTOR,
    {
      provideSignatureHelp(document, position) {
        const call = getCallContext(document, position);
        if (!call) {
          return undefined;
        }

        const match = findFunctionByName(document.uri, call.name, workspaceFunctionCache);
        if (!match) {
          return undefined;
        }

        const signature = new vscode.SignatureInformation(`fun ${match.signature}`);
        signature.parameters = match.params.map((param) => new vscode.ParameterInformation(param));
        if (match.comment) {
          signature.documentation = new vscode.MarkdownString(match.comment);
        }

        const help = new vscode.SignatureHelp();
        help.signatures = [signature];
        help.activeSignature = 0;
        help.activeParameter = Math.min(call.argumentIndex, Math.max(0, match.params.length - 1));
        return help;
      }
    },
    "(",
    ","
  );

  const quickFixProvider = vscode.languages.registerCodeActionsProvider(
    SIMPLEC_SELECTOR,
    {
      provideCodeActions(document, _range, contextForAction) {
        const actions: vscode.CodeAction[] = [];
        for (const diagnostic of contextForAction.diagnostics) {
          if (diagnostic.code === UNKNOWN_FUNCTION_DIAG_CODE && typeof diagnostic.message === "string") {
            const unknownName = extractUnknownFunctionName(diagnostic.message);
            if (!unknownName) {
              continue;
            }

            const action = new vscode.CodeAction(
              `Create function '${unknownName}'`,
              vscode.CodeActionKind.QuickFix
            );
            action.edit = new vscode.WorkspaceEdit();
            const insertPos = getFunctionStubInsertPosition(document);
            const stub = buildFunctionStub(unknownName);
            action.edit.insert(document.uri, insertPos, stub);
            action.diagnostics = [diagnostic];
            action.isPreferred = true;
            actions.push(action);
            continue;
          }

          if (diagnostic.code === MISSING_SEMICOLON_DIAG_CODE) {
            const action = new vscode.CodeAction("Insert ';'", vscode.CodeActionKind.QuickFix);
            action.edit = new vscode.WorkspaceEdit();
            action.edit.insert(document.uri, diagnostic.range.end, ";");
            action.diagnostics = [diagnostic];
            action.isPreferred = true;
            actions.push(action);
            continue;
          }

          if (diagnostic.code === UNCLOSED_BRACE_DIAG_CODE) {
            const action = new vscode.CodeAction("Add missing '}'", vscode.CodeActionKind.QuickFix);
            action.edit = new vscode.WorkspaceEdit();
            action.edit.insert(document.uri, getFunctionStubInsertPosition(document), "\n}");
            action.diagnostics = [diagnostic];
            action.isPreferred = true;
            actions.push(action);
            continue;
          }

          if (diagnostic.code === UNCLOSED_PAREN_DIAG_CODE) {
            const action = new vscode.CodeAction("Add missing ')'", vscode.CodeActionKind.QuickFix);
            action.edit = new vscode.WorkspaceEdit();
            action.edit.insert(document.uri, getFunctionStubInsertPosition(document), ")");
            action.diagnostics = [diagnostic];
            action.isPreferred = true;
            actions.push(action);
            continue;
          }

          if (diagnostic.code === WRONG_ARGUMENT_COUNT_DIAG_CODE) {
            const action = new vscode.CodeAction(
              "Check function signature in hover or definition",
              vscode.CodeActionKind.QuickFix
            );
            action.diagnostics = [diagnostic];
            actions.push(action);
            continue;
          }
        }

        return actions;
      }
    },
    {
      providedCodeActionKinds: [vscode.CodeActionKind.QuickFix]
    }
  );

  const definitionProvider = vscode.languages.registerDefinitionProvider(SIMPLEC_SELECTOR, {
    async provideDefinition(document, position) {
      const symbolRange = document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/);
      if (!symbolRange) {
        return undefined;
      }

      const symbol = document.getText(symbolRange);
      if (!isLikelyFunctionSymbol(document, symbolRange) || SIMPLEC_KEYWORDS.has(symbol)) {
        return undefined;
      }

      const allFunctions = await collectAllWorkspaceFunctions(functionIndex);
      const sameDocument = allFunctions.find((fn) => fn.name === symbol && fn.uri.toString() === document.uri.toString());
      if (sameDocument) {
        return new vscode.Location(sameDocument.uri, sameDocument.nameRange);
      }

      const match = allFunctions.find((fn) => fn.name === symbol);
      if (!match) {
        return undefined;
      }

      return new vscode.Location(match.uri, match.nameRange);
    }
  });

  const renameProvider = vscode.languages.registerRenameProvider(SIMPLEC_SELECTOR, {
    async provideRenameEdits(document, position, newName) {
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(newName)) {
        throw new Error("SimpleC function names must match [A-Za-z_][A-Za-z0-9_]*.");
      }

      const symbolRange = document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/);
      if (!symbolRange) {
        throw new Error("Place the cursor on a function name to rename it.");
      }

      const oldName = document.getText(symbolRange);
      if (SIMPLEC_KEYWORDS.has(oldName)) {
        throw new Error("Cannot rename language keywords.");
      }

      const allFunctions = await collectAllWorkspaceFunctions(functionIndex);
      if (!allFunctions.some((fn) => fn.name === oldName)) {
        throw new Error(`Function '${oldName}' was not found in the workspace.`);
      }

      const edit = new vscode.WorkspaceEdit();
      const allSources = await collectSimpleCSources();
      for (const source of allSources) {
        for (const range of findFunctionNameOccurrences(source.text, oldName)) {
          edit.replace(source.uri, range, newName);
        }
      }

      return edit;
    },
    prepareRename(document, position) {
      const symbolRange = document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/);
      if (!symbolRange) {
        throw new Error("Place the cursor on a function name to rename it.");
      }

      const symbol = document.getText(symbolRange);
      if (SIMPLEC_KEYWORDS.has(symbol)) {
        throw new Error("Cannot rename language keywords.");
      }

      return symbolRange;
    }
  });

  const scheduleValidation = (document: vscode.TextDocument, delayMs = 200): void => {
    if (document.languageId !== "simplec") {
      return;
    }

    const key = document.uri.toString();
    const existing = pendingValidationTimers.get(key);
    if (existing) {
      clearTimeout(existing);
    }

    const timer = setTimeout(() => {
      pendingValidationTimers.delete(key);
      void validateDocument(document, diagnostics, functionIndex, stdlibFunctionNames, context).then((allFunctions) => {
        workspaceFunctionCache = allFunctions;
      });
    }, delayMs);
    pendingValidationTimers.set(key, timer);
  };

  const closeDocument = (document: vscode.TextDocument): void => {
    if (document.languageId !== "simplec") {
      return;
    }
    const key = document.uri.toString();
    const existing = pendingValidationTimers.get(key);
    if (existing) {
      clearTimeout(existing);
      pendingValidationTimers.delete(key);
    }
    functionIndex.delete(key);
    workspaceFunctionCache = workspaceFunctionCache.filter((fn) => fn.uri.toString() !== key);
    diagnostics.delete(document.uri);
  };

  for (const document of vscode.workspace.textDocuments) {
    scheduleValidation(document, 0);
  }

  context.subscriptions.push(
    output,
    diagnostics,
    hoverProvider,
    signatureProvider,
    quickFixProvider,
    definitionProvider,
    renameProvider,
    vscode.workspace.onDidOpenTextDocument((document) => {
      scheduleValidation(document, 0);
    }),
    vscode.workspace.onDidChangeTextDocument((event) => {
      scheduleValidation(event.document, 250);
    }),
    vscode.workspace.onDidSaveTextDocument((document) => {
      scheduleValidation(document, 0);
    }),
    vscode.workspace.onDidCloseTextDocument((document) => {
      closeDocument(document);
    }),
    vscode.commands.registerCommand("simplec.parseCurrentFile", async () => {
      const file = await requireActiveFile();
      if (!file) {
        return;
      }
      await runAndReport(["parse", file], path.dirname(file));
    }),
    vscode.commands.registerCommand("simplec.runCurrentFile", async () => {
      const file = await requireActiveFile();
      if (!file) {
        return;
      }
      await runAndReport(["run", file], path.dirname(file));
    }),
    vscode.commands.registerCommand("simplec.compileCurrentFile", async () => {
      const file = await requireActiveFile();
      if (!file) {
        return;
      }
      const defaultOutput = `${file}.sbc.json`;
      const outputPath = await vscode.window.showInputBox({
        prompt: "Bytecode output file path",
        value: defaultOutput,
        ignoreFocusOut: true,
      });

      if (!outputPath) {
        return;
      }

      await runAndReport(["compile", file, "-o", outputPath, "-f"], path.dirname(file));
    }),
    vscode.commands.registerCommand("simplec.runBytecodeFile", async () => {
      const selected = await vscode.window.showOpenDialog({
        canSelectFolders: false,
        canSelectFiles: true,
        canSelectMany: false,
        title: "Select SimpleC bytecode file",
        filters: {
          "Bytecode files": ["json", "sbc"],
          "All files": ["*"]
        }
      });

      if (!selected || selected.length === 0) {
        return;
      }

      await runAndReport(["run-bytecode", selected[0].fsPath], path.dirname(selected[0].fsPath));
    }),
    vscode.commands.registerCommand("simplec.runTests", async () => {
      await runAndReport(["tests"], getBundledRoot(context));
    })
  );

  async function runAndReport(commandArgs: string[], cwd: string): Promise<void> {
    try {
      const config = getConfig();
      const workspaceRoot = getWorkspaceFolder()?.uri.fsPath;
      const resolvedCliPath = resolveCliPath(config, context, workspaceRoot);
      output.show(true);
      output.appendLine(`$ ${config.pythonPath} ${[resolvedCliPath, ...config.additionalArgs, ...commandArgs].join(" ")}`);

      const result = await runSimpleC(
        config.pythonPath,
        resolvedCliPath,
        [...config.additionalArgs, ...commandArgs],
        cwd
      );

      if (result.stdout.trim().length > 0) {
        output.appendLine(result.stdout.trimEnd());
      }
      if (result.stderr.trim().length > 0) {
        output.appendLine(result.stderr.trimEnd());
      }
      output.appendLine(`(exit code: ${result.exitCode})`);

      if (result.exitCode === 0) {
        vscode.window.showInformationMessage("SimpleC command finished successfully.");
      } else {
        vscode.window.showErrorMessage("SimpleC command failed. See output channel for details.");
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      output.appendLine(message);
      vscode.window.showErrorMessage(`SimpleC error: ${message}`);
    }
  }
}

function getConfig(): SimpleCConfig {
  const cfg = vscode.workspace.getConfiguration("simplec");
  const runtimeMode = cfg.get<string>("runtimeMode", "bundled");
  return {
    pythonPath: cfg.get<string>("pythonPath", "python"),
    runtimeMode: runtimeMode === "workspace" || runtimeMode === "custom" ? runtimeMode : "bundled",
    workspaceCliPath: cfg.get<string>("workspaceCliPath", "main.py"),
    customCliPath: cfg.get<string>("customCliPath", ""),
    additionalArgs: cfg.get<string[]>("additionalArgs", []),
  };
}

function getWorkspaceFolder(): vscode.WorkspaceFolder | undefined {
  return vscode.workspace.workspaceFolders?.[0];
}

function getBundledRoot(context: vscode.ExtensionContext): string {
  return path.join(context.extensionPath, "bundled");
}

function resolveCliPath(
  config: SimpleCConfig,
  context: vscode.ExtensionContext,
  workspaceRoot?: string
): string {
  if (config.runtimeMode === "bundled") {
    return path.join(getBundledRoot(context), "main.py");
  }

  if (config.runtimeMode === "workspace") {
    if (!workspaceRoot) {
      throw new Error("No workspace folder is open. Switch simplec.runtimeMode to bundled or open a workspace.");
    }
    return resolvePath(config.workspaceCliPath, workspaceRoot);
  }

  if (config.customCliPath.trim().length === 0) {
    throw new Error("simplec.customCliPath is empty. Set it in settings when runtimeMode is custom.");
  }

  return resolvePath(config.customCliPath, workspaceRoot);
}

function resolvePath(pathValue: string, workspaceRoot?: string): string {
  if (path.isAbsolute(pathValue)) {
    return pathValue;
  }

  if (workspaceRoot) {
    const expanded = pathValue.replace("${workspaceFolder}", workspaceRoot);
    if (path.isAbsolute(expanded)) {
      return expanded;
    }
    return path.join(workspaceRoot, expanded);
  }

  return path.resolve(pathValue);
}

async function requireActiveFile(): Promise<string | undefined> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showErrorMessage("Open a SimpleC source file first.");
    return undefined;
  }

  if (editor.document.isUntitled) {
    const saved = await editor.document.save();
    if (!saved) {
      vscode.window.showWarningMessage("Save the current file before running SimpleC commands.");
      return undefined;
    }
  }

  return editor.document.uri.fsPath;
}

function runSimpleC(
  pythonPath: string,
  cliPath: string,
  args: string[],
  cwd: string
): Promise<RunResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonPath, [cliPath, ...args], {
      cwd,
      shell: false,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    child.on("error", (err) => {
      reject(err);
    });

    child.on("close", (exitCode) => {
      resolve({
        exitCode: exitCode ?? 1,
        stdout,
        stderr,
      });
    });
  });
}

export function deactivate(): void {
  // Nothing to clean up.
}

async function validateDocument(
  document: vscode.TextDocument,
  diagnostics: vscode.DiagnosticCollection,
  functionIndex: Map<string, FunctionInfo[]>,
  stdlibFunctionNames: Set<string>,
  context: vscode.ExtensionContext
): Promise<FunctionInfo[]> {
  if (document.languageId !== "simplec") {
    return [];
  }

  const versionAtStart = document.version;
  const functions = parseFunctionDefinitions(document);
  functionIndex.set(document.uri.toString(), functions);

  const allFunctions = await collectAllWorkspaceFunctions(functionIndex);

  const parserDiagnostics = await getParserDiagnostics(document, context);
  if (document.version !== versionAtStart) {
    return allFunctions;
  }

  const semanticDiagnostics = getUnknownFunctionDiagnostics(document, functions, stdlibFunctionNames);
  const arityDiagnostics = getArgumentCountDiagnostics(document, allFunctions, stdlibFunctionNames);
  const syntaxHintDiagnostics = getSyntaxHintDiagnostics(document, parserDiagnostics[0]);
  diagnostics.set(document.uri, [...parserDiagnostics, ...syntaxHintDiagnostics, ...semanticDiagnostics, ...arityDiagnostics]);
  return allFunctions;
}

function parseFunctionDefinitions(document: vscode.TextDocument): FunctionInfo[] {
  return parseFunctionDefinitionsFromText(document.uri, document.getText());
}

function parseFunctionDefinitionsFromText(uri: vscode.Uri, source: string): FunctionInfo[] {
  const lines = source.split(/\r?\n/);
  const functionPattern = /^\s*fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*([^\s{][^{]*)\s*\{/;
  const functionInfos: FunctionInfo[] = [];

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    const match = line.match(functionPattern);
    if (!match) {
      continue;
    }

    const name = match[1];
    const paramsRaw = match[2].trim();
    const returnType = match[3].trim();
    const params = paramsRaw.length === 0
      ? []
      : paramsRaw.split(",").map((part) => part.trim()).filter((part) => part.length > 0);
    const signature = `${name}(${params.join(", ")}) ${returnType}`;

    const nameStartCol = line.indexOf(name);
    const nameRange = new vscode.Range(
      new vscode.Position(lineIndex, Math.max(0, nameStartCol)),
      new vscode.Position(lineIndex, Math.max(0, nameStartCol) + name.length)
    );

    const commentLines: string[] = [];
    for (let commentLine = lineIndex - 1; commentLine >= 0; commentLine -= 1) {
      const trimmed = lines[commentLine].trim();
      if (trimmed.length === 0) {
        if (commentLines.length > 0) {
          break;
        }
        continue;
      }
      if (!trimmed.startsWith("##")) {
        break;
      }
      commentLines.unshift(trimmed.replace(/^##\s?/, ""));
    }

    functionInfos.push({
      name,
      params,
      returnType,
      signature,
      comment: commentLines.length > 0 ? commentLines.join("\n") : undefined,
      nameRange,
      uri,
    });
  }

  return functionInfos;
}

function getSyntaxHintDiagnostics(
  document: vscode.TextDocument,
  parserDiagnostic?: vscode.Diagnostic
): vscode.Diagnostic[] {
  if (!parserDiagnostic) {
    return [];
  }

  const hints: vscode.Diagnostic[] = [];
  const parseLine = Math.max(0, parserDiagnostic.range.start.line);
  const lineText = parseLine < document.lineCount ? document.lineAt(parseLine).text : "";
  const trimmed = lineText.trim();

  if (trimmed.length > 0 && !/;\s*$/.test(trimmed) && !/[{}]\s*$/.test(trimmed) && !isCompoundStatementLine(trimmed)) {
    const semiPos = new vscode.Position(parseLine, lineText.length);
    const hint = new vscode.Diagnostic(
      new vscode.Range(semiPos, semiPos),
      "Possible missing ';' at end of statement.",
      vscode.DiagnosticSeverity.Hint
    );
    hint.code = MISSING_SEMICOLON_DIAG_CODE;
    hint.source = "simplec";
    hints.push(hint);
  }

  const content = document.getText();
  const braceBalance = computeTokenBalance(content, "{", "}");
  if (braceBalance > 0) {
    const last = getFunctionStubInsertPosition(document);
    const hint = new vscode.Diagnostic(
      new vscode.Range(last, last),
      "Possible missing closing '}' at end of file.",
      vscode.DiagnosticSeverity.Hint
    );
    hint.code = UNCLOSED_BRACE_DIAG_CODE;
    hint.source = "simplec";
    hints.push(hint);
  }

  const parenBalance = computeTokenBalance(content, "(", ")");
  if (parenBalance > 0) {
    const last = getFunctionStubInsertPosition(document);
    const hint = new vscode.Diagnostic(
      new vscode.Range(last, last),
      "Possible missing closing ')' at end of file.",
      vscode.DiagnosticSeverity.Hint
    );
    hint.code = UNCLOSED_PAREN_DIAG_CODE;
    hint.source = "simplec";
    hints.push(hint);
  }

  return hints;
}

function isCompoundStatementLine(trimmed: string): boolean {
  return /^(if|elif|else|while|for|fun|try|catch)\b/.test(trimmed);
}

function computeTokenBalance(source: string, openToken: string, closeToken: string): number {
  let balance = 0;
  for (const ch of source) {
    if (ch === openToken) {
      balance += 1;
      continue;
    }
    if (ch === closeToken) {
      balance -= 1;
    }
  }
  return Math.max(0, balance);
}

function getUnknownFunctionDiagnostics(
  document: vscode.TextDocument,
  functions: FunctionInfo[],
  stdlibFunctionNames: Set<string>
): vscode.Diagnostic[] {
  const diagnostics: vscode.Diagnostic[] = [];
  const knownNames = new Set(functions.map((fn) => fn.name));
  for (const stdlibName of stdlibFunctionNames) {
    knownNames.add(stdlibName);
  }

  const callPattern = /\b([A-Za-z_][A-Za-z0-9_]*)\s*\(/g;
  for (let lineIndex = 0; lineIndex < document.lineCount; lineIndex += 1) {
    const line = document.lineAt(lineIndex).text;
    let match: RegExpExecArray | null;
    while ((match = callPattern.exec(line)) !== null) {
      const fnName = match[1];
      if (SIMPLEC_KEYWORDS.has(fnName) || knownNames.has(fnName)) {
        continue;
      }

      const start = new vscode.Position(lineIndex, match.index);
      const end = new vscode.Position(lineIndex, match.index + fnName.length);
      const diag = new vscode.Diagnostic(
        new vscode.Range(start, end),
        `Unknown function '${fnName}'.`,
        vscode.DiagnosticSeverity.Warning
      );
      diag.code = UNKNOWN_FUNCTION_DIAG_CODE;
      diag.source = "simplec";
      diagnostics.push(diag);
    }
  }

  return diagnostics;
}

function getArgumentCountDiagnostics(
  document: vscode.TextDocument,
  allFunctions: FunctionInfo[],
  stdlibFunctionNames: Set<string>
): vscode.Diagnostic[] {
  const diagnostics: vscode.Diagnostic[] = [];
  const knownNames = new Set(allFunctions.map((fn) => fn.name));
  for (const stdlibName of stdlibFunctionNames) {
    knownNames.add(stdlibName);
  }

  const lines = document.getText().split(/\r?\n/);
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    const callPattern = /\b([A-Za-z_][A-Za-z0-9_]*)\s*\(/g;
    let match: RegExpExecArray | null;
    while ((match = callPattern.exec(line)) !== null) {
      const fnName = match[1];
      if (SIMPLEC_KEYWORDS.has(fnName) || !knownNames.has(fnName)) {
        continue;
      }

      const openParenCol = match.index + match[0].length - 1;
      const closingParenCol = findClosingParenOnLine(line, openParenCol);
      if (closingParenCol < 0) {
        continue;
      }

      const argsText = line.slice(openParenCol + 1, closingParenCol);
      const actualCount = countTopLevelArguments(argsText);
      const expected = findFunctionByName(document.uri, fnName, allFunctions);
      if (!expected) {
        continue;
      }

      const expectedCount = expected.params.length;
      if (actualCount === expectedCount) {
        continue;
      }

      const start = new vscode.Position(lineIndex, match.index);
      const end = new vscode.Position(lineIndex, match.index + fnName.length);
      const diag = new vscode.Diagnostic(
        new vscode.Range(start, end),
        `Function '${fnName}' expects ${expectedCount} argument(s) but got ${actualCount}.`,
        vscode.DiagnosticSeverity.Error
      );
      diag.code = WRONG_ARGUMENT_COUNT_DIAG_CODE;
      diag.source = "simplec";
      diagnostics.push(diag);
    }
  }

  return diagnostics;
}

function findClosingParenOnLine(line: string, openParenCol: number): number {
  let depth = 0;
  for (let i = openParenCol; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === "(") {
      depth += 1;
      continue;
    }
    if (ch === ")") {
      depth -= 1;
      if (depth === 0) {
        return i;
      }
    }
  }
  return -1;
}

function countTopLevelArguments(argsText: string): number {
  const trimmed = argsText.trim();
  if (trimmed.length === 0) {
    return 0;
  }

  let depthParen = 0;
  let depthBracket = 0;
  let count = 1;
  for (const ch of argsText) {
    if (ch === "(") {
      depthParen += 1;
      continue;
    }
    if (ch === ")") {
      depthParen = Math.max(0, depthParen - 1);
      continue;
    }
    if (ch === "[") {
      depthBracket += 1;
      continue;
    }
    if (ch === "]") {
      depthBracket = Math.max(0, depthBracket - 1);
      continue;
    }
    if (ch === "," && depthParen === 0 && depthBracket === 0) {
      count += 1;
    }
  }

  return count;
}

function findFunctionByName(
  currentUri: vscode.Uri,
  functionName: string,
  functions: FunctionInfo[]
): FunctionInfo | undefined {
  const sameDocument = functions.find(
    (fn) => fn.name === functionName && fn.uri.toString() === currentUri.toString()
  );
  if (sameDocument) {
    return sameDocument;
  }

  return functions.find((fn) => fn.name === functionName);
}

async function getParserDiagnostics(
  document: vscode.TextDocument,
  context: vscode.ExtensionContext
): Promise<vscode.Diagnostic[]> {
  const config = getConfig();
  const workspaceRoot = getWorkspaceFolder()?.uri.fsPath;
  const cliPath = resolveCliPath(config, context, workspaceRoot);
  const moduleRoot = path.dirname(cliPath);

  const parserCheck = await runParserCheck(config.pythonPath, moduleRoot, document.getText(), moduleRoot);
  if (parserCheck.ok || !parserCheck.error) {
    return [];
  }

  const zeroBasedLine = Math.max(0, parserCheck.error.line - 1);
  const zeroBasedCol = Math.max(0, parserCheck.error.column - 1);
  const lineText = zeroBasedLine < document.lineCount ? document.lineAt(zeroBasedLine).text : "";
  const endCol = Math.min(lineText.length, zeroBasedCol + 1);

  const diagnostic = new vscode.Diagnostic(
    new vscode.Range(
      new vscode.Position(zeroBasedLine, Math.min(zeroBasedCol, lineText.length)),
      new vscode.Position(zeroBasedLine, Math.max(Math.min(zeroBasedCol + 1, lineText.length), endCol))
    ),
    parserCheck.error.message,
    vscode.DiagnosticSeverity.Error
  );
  diagnostic.source = "simplec";

  return [diagnostic];
}

function getCallContext(
  document: vscode.TextDocument,
  position: vscode.Position
): { name: string; argumentIndex: number } | undefined {
  const line = document.lineAt(position.line).text;
  const prefix = line.slice(0, position.character);
  const callMatch = prefix.match(/([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()]*)$/);
  if (!callMatch) {
    return undefined;
  }

  const name = callMatch[1];
  if (SIMPLEC_KEYWORDS.has(name)) {
    return undefined;
  }

  const argsSoFar = callMatch[2].trim();
  const argumentIndex = argsSoFar.length === 0 ? 0 : argsSoFar.split(",").length - 1;
  return { name, argumentIndex };
}

function isLikelyFunctionSymbol(document: vscode.TextDocument, range: vscode.Range): boolean {
  const line = document.lineAt(range.start.line).text;
  const afterWord = line.slice(range.end.character);
  if (/^\s*\(/.test(afterWord)) {
    return true;
  }

  const beforeWord = line.slice(0, range.start.character);
  if (/\bfun\s+$/.test(beforeWord)) {
    return true;
  }

  return false;
}

function extractUnknownFunctionName(message: string): string | undefined {
  const match = message.match(/^Unknown function '([A-Za-z_][A-Za-z0-9_]*)'\.$/);
  return match?.[1];
}

function getFunctionStubInsertPosition(document: vscode.TextDocument): vscode.Position {
  if (document.lineCount === 0) {
    return new vscode.Position(0, 0);
  }

  const lastLine = document.lineAt(document.lineCount - 1);
  return new vscode.Position(lastLine.lineNumber, lastLine.text.length);
}

function buildFunctionStub(functionName: string): string {
  return `\n\n## TODO: describe ${functionName}\nfun ${functionName}(void value) void {\n    return void\n}\n`;
}

type SourceFileText = {
  uri: vscode.Uri;
  text: string;
};

async function collectSimpleCSources(): Promise<SourceFileText[]> {
  const sourceByUri = new Map<string, SourceFileText>();

  for (const doc of vscode.workspace.textDocuments) {
    if (doc.languageId !== "simplec") {
      continue;
    }
    sourceByUri.set(doc.uri.toString(), { uri: doc.uri, text: doc.getText() });
  }

  const files = await vscode.workspace.findFiles("**/*.{sc,glados}", "**/node_modules/**");
  for (const uri of files) {
    if (sourceByUri.has(uri.toString())) {
      continue;
    }
    try {
      const data = await fs.readFile(uri.fsPath, "utf8");
      sourceByUri.set(uri.toString(), { uri, text: data });
    } catch {
      // Ignore unreadable files.
    }
  }

  return [...sourceByUri.values()];
}

async function collectAllWorkspaceFunctions(
  functionIndex: Map<string, FunctionInfo[]>
): Promise<FunctionInfo[]> {
  const infos: FunctionInfo[] = [];

  for (const entries of functionIndex.values()) {
    infos.push(...entries);
  }

  const sources = await collectSimpleCSources();
  for (const source of sources) {
    if (functionIndex.has(source.uri.toString())) {
      continue;
    }
    infos.push(...parseFunctionDefinitionsFromText(source.uri, source.text));
  }

  return infos;
}

function findFunctionNameOccurrences(source: string, functionName: string): vscode.Range[] {
  const escaped = functionName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const callPattern = new RegExp(`\\b${escaped}\\b\\s*\\(`, "g");
  const defPattern = new RegExp(`\\bfun\\s+${escaped}\\b\\s*\\(`, "g");
  const ranges: vscode.Range[] = [];

  const lines = source.split(/\r?\n/);
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];

    let callMatch: RegExpExecArray | null;
    while ((callMatch = callPattern.exec(line)) !== null) {
      const start = new vscode.Position(lineIndex, callMatch.index);
      const end = new vscode.Position(lineIndex, callMatch.index + functionName.length);
      ranges.push(new vscode.Range(start, end));
    }
    callPattern.lastIndex = 0;

    let defMatch: RegExpExecArray | null;
    while ((defMatch = defPattern.exec(line)) !== null) {
      const nameOffset = defMatch[0].indexOf(functionName);
      const startCol = defMatch.index + Math.max(0, nameOffset);
      const start = new vscode.Position(lineIndex, startCol);
      const end = new vscode.Position(lineIndex, startCol + functionName.length);
      ranges.push(new vscode.Range(start, end));
    }
    defPattern.lastIndex = 0;
  }

  return ranges;
}

async function loadStdlibFunctionNames(context: vscode.ExtensionContext): Promise<Set<string>> {
  const names = new Set<string>();
  const roots = new Set<string>();

  const workspaceRoot = getWorkspaceFolder()?.uri.fsPath;
  if (workspaceRoot) {
    roots.add(path.join(workspaceRoot, "standard_lib"));
  }
  roots.add(path.join(getBundledRoot(context), "standard_lib"));

  for (const root of roots) {
    try {
      const entries = await fs.readdir(root, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isFile() || !entry.name.endsWith(".glados")) {
          continue;
        }

        const filePath = path.join(root, entry.name);
        const text = await fs.readFile(filePath, "utf8");
        const matches = text.matchAll(/^\s*fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm);
        for (const match of matches) {
          const fnName = match[1];
          if (fnName) {
            names.add(fnName);
          }
        }
      }
    } catch {
      // Ignore missing stdlib directories.
    }
  }

  return names;
}

function runParserCheck(
  pythonPath: string,
  moduleRoot: string,
  source: string,
  cwd: string
): Promise<ParserCheckResult> {
  const script = [
    "import json",
    "import sys",
    "sys.path.insert(0, sys.argv[1])",
    "payload = {'ok': False, 'message': 'Unknown parser error', 'line': 1, 'column': 1}",
    "try:",
    "    from code_to_ast.parser import parse_code",
    "except Exception as exc:",
    "    payload['message'] = f'Failed to load parser: {exc}'",
    "    print(json.dumps(payload))",
    "    raise SystemExit(0)",
    "source = sys.stdin.read()",
    "try:",
    "    parse_code(source)",
    "    print(json.dumps({'ok': True}))",
    "except Exception as exc:",
    "    payload['message'] = str(exc)",
    "    payload['line'] = int(getattr(exc, 'line', 1) or 1)",
    "    payload['column'] = int(getattr(exc, 'column', 1) or 1)",
    "    print(json.dumps(payload))",
  ].join("\n");

  return new Promise((resolve) => {
    const child = spawn(pythonPath, ["-c", script, moduleRoot], {
      cwd,
      shell: false,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    child.on("error", (err) => {
      resolve({
        ok: false,
        error: {
          message: `Failed to run parser check: ${err.message}`,
          line: 1,
          column: 1,
        }
      });
    });

    child.on("close", () => {
      const outputLines = stdout
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
      const jsonLine = outputLines.length > 0 ? outputLines[outputLines.length - 1] : "";

      try {
        const parsed = JSON.parse(jsonLine) as ParserCheckResult & { line?: number; column?: number };
        if (parsed.ok) {
          resolve({ ok: true });
          return;
        }

        resolve({
          ok: false,
          error: {
            message: parsed.message ?? "Parser error",
            line: parsed.line ?? 1,
            column: parsed.column ?? 1,
          }
        });
      } catch {
        resolve({
          ok: false,
          error: {
            message: stderr.trim().length > 0 ? stderr.trim() : "Could not parse parser output.",
            line: 1,
            column: 1,
          }
        });
      }
    });

    child.stdin.write(source);
    child.stdin.end();
  });
}
