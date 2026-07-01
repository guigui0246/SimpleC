# SimpleC VS Code Extension

This extension adds SimpleC language support and project commands for your compiler.

## Features

- Syntax highlighting for `.sc` and `.glados`
- Live parser diagnostics for SimpleC syntax errors
- Semantic diagnostics for unknown function calls and wrong argument counts
- Quick fix to generate a missing function stub
- Parser-aware quick fixes for common syntax issues (missing `;`, unclosed `)` or `}`)
- Hover tooltips on functions with signature and `##` doc comments (including definitions from other files)
- Signature help while typing function arguments (including cross-file function definitions)
- Go to Definition for function calls
- Rename Symbol for function definitions and call sites
- Built-in bundled SimpleC runtime (default), so commands work even when your workspace does not contain the compiler source tree
- Command Palette commands:
  - `SimpleC: Parse Current File`
  - `SimpleC: Run Current File`
  - `SimpleC: Compile Current File`
  - `SimpleC: Run Bytecode File`
  - `SimpleC: Run Test Suite`
- Output logs in the `SimpleC` output channel

## Configuration

- `simplec.pythonPath`: Python executable (default: `python`)
- `simplec.runtimeMode`: `bundled`, `workspace`, or `custom` (default: `bundled`)
- `simplec.workspaceCliPath`: Path to workspace CLI entrypoint when runtime mode is `workspace`
- `simplec.customCliPath`: Path to custom CLI entrypoint when runtime mode is `custom`
- `simplec.additionalArgs`: Extra args inserted before each SimpleC command

## Development

From this folder:

```bash
npm install
npm run compile
```

`npm run compile` automatically regenerates `bundled/` from the root project (`main.py`, `code_to_ast`, `ast_to_bytecode`, `run_bytecode`, `standard_lib`, `tests`, `requirements.txt`) before TypeScript compilation.

Then press `F5` in VS Code to launch an Extension Development Host.

## Build VSIX (Installable Extension)

`npm run compile` only builds TypeScript output; it does not create an installable extension file.

To create a `.vsix` package:

```bash
npm run package
```

This generates a file like `simplec-tools-0.1.0.vsix` in this folder.

To install it locally:

```bash
code --install-extension simplec-tools-0.1.0.vsix
```

Or use the convenience script:

```bash
npm run install-local
```

You can also install manually in VS Code:

1. Open Extensions view
2. Click the `...` menu
3. Select `Install from VSIX...`
4. Pick the generated `.vsix` file
