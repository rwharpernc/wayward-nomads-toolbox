#!/usr/bin/env node
/**
 * Zip dist/WNTB (as a top-level WNTB/ folder) into dist/WNTB.zip for distribution.
 *
 * Usage:  node scripts/package.mjs   (run `npm run build` first)
 * Output: dist/WNTB.zip
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const sourceDir = path.join(root, "dist", "WNTB");

if (!fs.existsSync(sourceDir)) {
  console.error(`${sourceDir} does not exist — run "npm run build" first.`);
  process.exit(1);
}

const version = fs
  .readFileSync(path.join(root, "plugin", "__init__.py"), "utf8")
  .match(/__version__\s*=\s*["']([^"']+)["']/)?.[1] ?? "0.0.0";

const zipPath = path.join(root, "dist", "WNTB.zip");

if (fs.existsSync(zipPath)) {
  fs.rmSync(zipPath);
}

// Zip the WNTB folder itself (unversioned archive name), so extracting into
// the EDMC plugins directory on any OS yields plugins/WNTB/. Entries are
// written by hand with forward slashes: Windows PowerShell 5.1's
// Compress-Archive uses backslashes, which Linux/macOS unzip tools treat as
// part of a literal filename instead of creating directories.
const script = `
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$src = (Resolve-Path $env:WNTB_SRC).Path
$zip = [IO.Compression.ZipFile]::Open($env:WNTB_ZIP, 'Create')
try {
  Get-ChildItem -LiteralPath $src -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($src.Length + 1).Replace([string][char]92, '/')
    [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, "WNTB/$rel", 'Optimal')
  }
} finally { $zip.Dispose() }
`;
const result = spawnSync(
  "powershell.exe",
  ["-NoProfile", "-NonInteractive", "-Command", script],
  { stdio: "inherit", env: { ...process.env, WNTB_SRC: sourceDir, WNTB_ZIP: zipPath } },
);

if (result.status !== 0) {
  console.error("Zipping failed.");
  process.exit(result.status ?? 1);
}

console.log(`Packaged WNTB v${version} -> ${zipPath}`);
