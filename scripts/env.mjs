/**
 * Environment detection shared by the build scripts: where EDMC keeps its
 * plugins folder on this machine (Windows, Linux native/Flatpak, macOS).
 *
 * Override with the WNTB_PLUGINS_DIR environment variable (the folder that
 * contains the plugins, e.g. ".../EDMarketConnector/plugins"), or by passing
 * --plugins-dir <path> to build.mjs.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export function candidatePluginDirs() {
  const home = os.homedir();
  switch (process.platform) {
    case "win32": {
      const local = process.env.LOCALAPPDATA ?? path.join(home, "AppData", "Local");
      return [{ label: "Windows", dir: path.join(local, "EDMarketConnector", "plugins") }];
    }
    case "darwin":
      return [
        {
          label: "macOS",
          dir: path.join(home, "Library", "Application Support", "EDMarketConnector", "plugins"),
        },
      ];
    default: {
      const dataHome = process.env.XDG_DATA_HOME || path.join(home, ".local", "share");
      return [
        { label: "Linux (native)", dir: path.join(dataHome, "EDMarketConnector", "plugins") },
        {
          label: "Linux (Flatpak)",
          dir: path.join(home, ".var", "app", "io.edcd.EDMarketConnector", "data", "EDMarketConnector", "plugins"),
        },
      ];
    }
  }
}

/** The plugins folder to use: explicit override, else the first existing candidate, else the first candidate. */
export function resolvePluginsDir(override) {
  const explicit = override || process.env.WNTB_PLUGINS_DIR;
  if (explicit) return { label: "override", dir: path.resolve(explicit), exists: fs.existsSync(explicit) };
  const candidates = candidatePluginDirs();
  const found = candidates.find((c) => fs.existsSync(c.dir));
  const pick = found ?? candidates[0];
  return { ...pick, exists: Boolean(found) };
}

export function platformName() {
  return { win32: "Windows", darwin: "macOS", linux: "Linux" }[process.platform] ?? process.platform;
}
