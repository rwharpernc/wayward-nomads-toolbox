#!/usr/bin/env node
/**
 * Build WNTB into dist/WNTB for copying into the EDMC plugins folder.
 *
 * Usage:  node scripts/build.mjs
 * Output: dist/WNTB/
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const sourceDir = path.join(root, "plugin");
const outputDir = path.join(root, "dist", "WNTB");

const SKIP_NAMES = new Set(["__pycache__", ".pyc"]);

function copyRecursive(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (SKIP_NAMES.has(entry.name)) continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyRecursive(srcPath, destPath);
    } else if (entry.isFile() && !entry.name.endsWith(".pyc")) {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function cleanDir(dir) {
  if (fs.existsSync(dir)) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

cleanDir(outputDir);
copyRecursive(sourceDir, outputDir);

// Good practice for the license to travel with the program itself, not
// just live in the source repo - copy it (and the third-party notices
// it points to) into the installable plugin folder too.
for (const name of ["LICENSE", "THIRD-PARTY-NOTICES.md"]) {
  fs.copyFileSync(path.join(root, name), path.join(outputDir, name));
}

const version = fs
  .readFileSync(path.join(sourceDir, "__init__.py"), "utf8")
  .match(/__version__\s*=\s*["']([^"']+)["']/)?.[1];

console.log(`Built WNTB v${version ?? "?"} -> ${outputDir}`);
console.log("");
console.log("Copy to EDMC plugins folder:");
console.log("  %LOCALAPPDATA%\\EDMarketConnector\\plugins\\WNTB");
