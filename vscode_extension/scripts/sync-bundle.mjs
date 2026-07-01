import { cp, mkdir, readdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const extensionRoot = path.resolve(__dirname, "..");
const projectRoot = path.resolve(extensionRoot, "..");
const bundleRoot = path.join(extensionRoot, "bundled");

const entriesToCopy = [
  "main.py",
  "requirements.txt",
  "ast_to_bytecode",
  "code_to_ast",
  "run_bytecode",
  "standard_lib",
];

async function pathExists(targetPath) {
  try {
    await readdir(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function ensureSourcesExist() {
  for (const entry of entriesToCopy) {
    const fullPath = path.join(projectRoot, entry);
    const parent = path.dirname(fullPath);
    const basename = path.basename(fullPath);
    const exists = await pathExists(parent);
    if (!exists) {
      throw new Error(`Missing expected source path: ${fullPath}`);
    }
    const siblings = await readdir(parent);
    if (!siblings.includes(basename)) {
      throw new Error(`Missing expected source path: ${fullPath}`);
    }
  }
}

async function syncBundle() {
  await ensureSourcesExist();

  await rm(bundleRoot, { recursive: true, force: true });
  await mkdir(bundleRoot, { recursive: true });

  for (const entry of entriesToCopy) {
    const src = path.join(projectRoot, entry);
    const dst = path.join(bundleRoot, entry);
    await cp(src, dst, {
      recursive: true,
      force: true,
      filter: (sourcePath) => {
        return !sourcePath.includes(`${path.sep}__pycache__${path.sep}`);
      },
    });
  }

  console.log(`Synced SimpleC bundle to: ${bundleRoot}`);
}

syncBundle().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
