// Ingest server: receives events from the Chrome extension and stores them in the capture DB, which
// it is the only writer of (D-015). It makes no LLM calls and runs no analysis; the Python side reads
// the DB read-only. Start: `npm --prefix ux-extension start`
import { randomUUID } from "node:crypto";
import http from "node:http";
import { pathToFileURL } from "node:url";
import { config } from "./config.js";
import {
  type DB,
  type SessionRow,
  createSession,
  endSession,
  findOpenSession,
  getDb,
  insertJudgeEvent,
  insertSnapshot,
  lastSnapshot,
  latestSession,
  listJudgeEvents,
  listSnapshots,
  markAccepted,
  sessionWithJudgeEvent,
  touchSession,
  upsertProblem,
} from "./db.js";
import { htmlToText, normalizeJudge } from "./judge.js";
import { computeMetrics } from "./sessions.js";
import { categoryFromTags } from "./taxonomy.js";

export type IncomingEvent =
  | {
      type: "problem_view";
      slug: string;
      ts?: string;
      problem?: { title: string; frontend_id?: string; difficulty?: string; tags?: string[]; content_html?: string; paid_only?: boolean };
    }
  | { type: "snapshot"; slug: string; ts?: string; language?: string; code: string; partial?: boolean }
  | { type: "judge"; slug: string; ts?: string; url?: string; data: Record<string, unknown>; code?: string; language?: string }
  | { type: "session_end"; slug: string; ts?: string; reason: "ended" };

export class Ingest {
  constructor(private readonly db: DB) {}

  handle(e: IncomingEvent): { session_id: string | null; ended?: boolean } {
    const ts = e.ts ?? new Date().toISOString();
    switch (e.type) {
      case "problem_view": {
        if (e.problem) {
          upsertProblem(this.db, {
            slug: e.slug,
            title: e.problem.title,
            frontend_id: e.problem.frontend_id,
            difficulty: e.problem.difficulty,
            tags: e.problem.tags,
            category: e.problem.tags?.length ? categoryFromTags(e.problem.tags, e.problem.title) : undefined,
            description: e.problem.content_html ? htmlToText(e.problem.content_html) : undefined,
            paid_only: e.problem.paid_only,
          });
        }
        return { session_id: this.openSession(e.slug, ts).id };
      }
      case "snapshot": {
        const s = this.openSession(e.slug, ts);
        this.addSnapshot(s.id, ts, e.code, e.language ?? null, e.partial);
        return { session_id: s.id };
      }
      case "judge": {
        const j = normalizeJudge(e.data, e.url);
        // Already stored (a repeated final poll, or a backfill of a result the hook caught): do
        // nothing. Checked before choosing a session, so a repeat that arrives after an Accepted
        // ended the session can't open a phantom session (T-001).
        if (j.submission_id) {
          const seen = sessionWithJudgeEvent(this.db, e.slug, j.submission_id);
          if (seen) return { session_id: seen };
        }
        // A result backfilled from LeetCode after you ended the session belongs to that session.
        const past = this.endedSessionAt(e.slug, ts);
        const s = past ?? this.openSession(e.slug, ts);
        const language = e.language ?? j.language;
        if (e.code) this.addSnapshot(s.id, ts, e.code, language);
        insertJudgeEvent(this.db, { session_id: s.id, ts, ...j, language });
        touchSession(this.db, s.id, ts);
        if (j.kind === "submit" && j.status === "Accepted") {
          if (past) this.markAcceptedLate(past);
          else this.finish(s.id, ts, "accepted");
          return { session_id: s.id, ended: true };
        }
        return { session_id: s.id };
      }
      case "session_end": {
        const s = findOpenSession(this.db, e.slug);
        if (!s) return { session_id: null };
        this.finish(s.id, ts, "ended");
        return { session_id: s.id, ended: true };
      }
    }
  }

  /** The open session for a slug, or a new one if none is open (or the open one went idle). */
  private openSession(slug: string, ts: string): SessionRow {
    const open = findOpenSession(this.db, slug);
    if (open) {
      const idleMin = (Date.parse(ts) - Date.parse(open.last_activity_at)) / 60_000;
      if (idleMin <= config.idleMinutes) return open;
      this.finish(open.id, open.last_activity_at, "idle");
    }
    return createSession(this.db, randomUUID(), slug, ts);
  }

  /** The ended session whose time span contains `ts`, if no session is open for the slug. */
  private endedSessionAt(slug: string, ts: string): SessionRow | undefined {
    if (findOpenSession(this.db, slug)) return undefined;
    const s = latestSession(this.db, slug);
    return s?.ended_at && s.started_at <= ts && ts <= s.ended_at ? s : undefined;
  }

  /** An Accepted submit turned up for a session already ended another way: record it as accepted. */
  private markAcceptedLate(s: SessionRow) {
    if (s.end_reason === "accepted") return;
    markAccepted(this.db, s.id);
    console.log(`session ${s.id} (${s.slug}) had a late Accepted submit; marked accepted`);
  }

  private addSnapshot(sessionId: string, ts: string, code: string, language: string | null, partial?: boolean) {
    if (lastSnapshot(this.db, sessionId)?.code === code) return; // unchanged
    insertSnapshot(this.db, { session_id: sessionId, ts, language, code, partial });
    touchSession(this.db, sessionId, ts);
  }

  finish(sessionId: string, ts: string, reason: string) {
    endSession(this.db, sessionId, ts, reason);
    console.log(`session ${sessionId} ended: ${reason}`);
  }

  /** End sessions with no activity for `idleMinutes`. */
  sweepIdle(now = new Date()) {
    const cutoff = new Date(now.getTime() - config.idleMinutes * 60_000).toISOString();
    const stale = this.db
      .prepare(`SELECT id, last_activity_at FROM sessions WHERE ended_at IS NULL AND last_activity_at < ?`)
      .all(cutoff) as Array<{ id: string; last_activity_at: string }>;
    for (const s of stale) this.finish(s.id, s.last_activity_at, "idle");
  }

  currentStatus(slug: string) {
    const open = findOpenSession(this.db, slug);
    const latest = open ?? latestSession(this.db, slug);
    if (!latest) return { session: null };
    const metrics = computeMetrics(latest, listSnapshots(this.db, latest.id), listJudgeEvents(this.db, latest.id));
    return { session: latest, metrics, open: !latest.ended_at };
  }
}

// ---- HTTP ----

function readJson(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

export function createServer(ingest: Ingest) {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    const send = (status: number, body: unknown) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(body));
    };
    try {
      if (req.method === "GET" && url.pathname === "/health") return send(200, { ok: true });
      if (req.method === "GET" && url.pathname === "/sessions/current") {
        const slug = url.searchParams.get("slug");
        if (!slug) return send(400, { error: "slug required" });
        return send(200, ingest.currentStatus(slug));
      }
      if (req.method === "POST" && url.pathname === "/events") {
        const body = (await readJson(req)) as IncomingEvent | { events: IncomingEvent[] };
        const events = "events" in body ? body.events : [body];
        const results = events.map((e) => ingest.handle(e));
        return send(200, { ok: true, results });
      }
      send(404, { error: "not found" });
    } catch (err) {
      console.error(err);
      send(500, { error: err instanceof Error ? err.message : String(err) });
    }
  });
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const db = getDb();
  const ingest = new Ingest(db);
  setInterval(() => ingest.sweepIdle(), 60_000).unref();
  createServer(ingest).listen(config.port, "127.0.0.1", () => {
    console.log(`ingest server on http://localhost:${config.port} · db ${config.dbPath}`);
  });
}
