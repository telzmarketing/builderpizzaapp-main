import { cp, stat } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const distDir = path.join(root, "dist");
const spaDir = path.join(distDir, "spa");

try {
  await stat(path.join(spaDir, "index.html"));
  await cp(spaDir, distDir, {
    recursive: true,
    force: true,
  });
  console.log("Prepared Capacitor webDir from dist/spa to dist.");
} catch (error) {
  console.warn("Skipped Capacitor webDir preparation:", error instanceof Error ? error.message : error);
}
