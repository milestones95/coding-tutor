import path from "node:path";
import { fileURLToPath } from "node:url";

/** ux-extension/ — this package's root. */
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
/** The repository root, one level up. The capture DB lives in its data/ folder (D-015). */
export const REPO_ROOT = path.resolve(ROOT, "..");

// Capture needs no secrets and makes no LLM calls, so it reads no .env (D-015, architecture §11).
export const config = {
  port: Number(process.env.PORT ?? 7777), // must match host_permissions in extension/manifest.json
  // The live capture DB. The ingest server is its only writer; the Python side opens it read-only.
  dbPath: process.env.LCA_DB ?? path.join(REPO_ROOT, "data", "capture.db"),
  idleMinutes: Number(process.env.LCA_IDLE_MINUTES ?? 30),
  // Gaps longer than this between activity events don't count toward active time.
  activityGapCapMinutes: 5,
};

export function localDate(d: Date): string {
  return d.toLocaleDateString("en-CA"); // YYYY-MM-DD in local time
}
