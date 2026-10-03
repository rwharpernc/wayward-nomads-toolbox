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
import zlib from "node:zlib";

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
// written by hand in pure Node (works on Windows and Linux alike) with forward
// slashes: Windows PowerShell 5.1's Compress-Archive uses backslashes, which
// Linux/macOS unzip tools treat as part of a literal filename.
function listFiles(dir, prefix = "") {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) out.push(...listFiles(path.join(dir, entry.name), rel));
    else if (entry.isFile()) out.push({ rel, full: path.join(dir, entry.name) });
  }
  return out;
}

function writeZip(files, dest) {
  const chunks = [];
  const central = [];
  let offset = 0;
  for (const { name, data } of files) {
    const nameBuf = Buffer.from(name, "utf8");
    const comp = zlib.deflateRawSync(data, { level: 9 });
    const crc = zlib.crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4); // version needed
    local.writeUInt16LE(0x0800, 6); // UTF-8 names
    local.writeUInt16LE(8, 8); // deflate
    local.writeUInt16LE(0, 10); // mod time
    local.writeUInt16LE(0x21, 12); // mod date (1980-01-01)
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(comp.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    chunks.push(local, nameBuf, comp);
    const cd = Buffer.alloc(46);
    cd.writeUInt32LE(0x02014b50, 0);
    cd.writeUInt16LE(20, 4); // version made by
    local.copy(cd, 6, 4, 30); // needed, flags, method, time, date, crc, sizes, name length
    cd.writeUInt32LE(offset, 42);
    central.push(cd, nameBuf);
    offset += local.length + nameBuf.length + comp.length;
  }
  const cdBuf = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(files.length, 8);
  end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(cdBuf.length, 12);
  end.writeUInt32LE(offset, 16);
  fs.writeFileSync(dest, Buffer.concat([...chunks, cdBuf, end]));
}

writeZip(
  listFiles(sourceDir).map(({ rel, full }) => ({ name: `WNTB/${rel}`, data: fs.readFileSync(full) })),
  zipPath,
);

console.log(`Packaged WNTB v${version} -> ${zipPath}`);
