// Builder unit tests for the trimmed ingest server (T-002). Run: npm --prefix ux-extension test
import assert from "node:assert/strict";
import { test } from "node:test";
import { openDb, type DB } from "../../../ux-extension/server/src/db.js";
import { Ingest } from "../../../ux-extension/server/src/ingest.js";

const SLUG = "unit-probe";

function fresh(): { db: DB; ingest: Ingest } {
  const db = openDb(":memory:");
  return { db, ingest: new Ingest(db) };
}

const runResult = {
  status_msg: "Accepted", state: "SUCCESS", correct_answer: true, total_correct: 1, total_testcases: 1,
  submission_id: "runcode_1.2_unit", task_name: "judger.runcodetask.RunCode", lang: "python3",
};
const acceptedSubmit = {
  status_msg: "Accepted", state: "SUCCESS", total_correct: 5, total_testcases: 5,
  submission_id: "1234567", task_name: "judger.judgetask.Judge", lang: "python3",
};

const session = (db: DB) =>
  db.prepare(`SELECT * FROM sessions WHERE slug = ?`).get(SLUG) as
    { id: string; end_reason: string | null; ended_at: string | null; analysis_status: string };

test("ending a session records the end and leaves analysis_status untouched", () => {
  const { db, ingest } = fresh();
  ingest.handle({ type: "snapshot", slug: SLUG, ts: "2026-01-05T10:00:00.000Z", code: "a" });
  ingest.handle({ type: "session_end", slug: SLUG, ts: "2026-01-05T10:05:00.000Z", reason: "ended" });
  const s = session(db);
  assert.equal(s.end_reason, "ended");
  assert.equal(s.ended_at, "2026-01-05T10:05:00.000Z");
  assert.equal(s.analysis_status, "open");
});

test("an Accepted submit ends the session as accepted", () => {
  const { db, ingest } = fresh();
  ingest.handle({ type: "snapshot", slug: SLUG, ts: "2026-01-05T10:00:00.000Z", code: "a" });
  const r = ingest.handle({ type: "judge", slug: SLUG, ts: "2026-01-05T10:01:00.000Z", data: acceptedSubmit });
  assert.equal(r.ended, true);
  assert.equal(session(db).end_reason, "accepted");
  const j = db.prepare(`SELECT kind, status, tests_passed FROM judge_events`).all();
  assert.deepEqual(j, [{ kind: "submit", status: "Accepted", tests_passed: 5 }]);
});

test("the same judge result arriving twice is stored once", () => {
  const { db, ingest } = fresh();
  const e = { type: "judge" as const, slug: SLUG, ts: "2026-01-05T10:01:00.000Z", data: runResult };
  ingest.handle(e);
  ingest.handle({ ...e, ts: "2026-01-05T10:01:01.000Z" });
  assert.equal((db.prepare(`SELECT COUNT(*) AS n FROM judge_events`).get() as { n: number }).n, 1);
});

test("a late Accepted marks an ended session accepted without deleting legacy attempts rows", () => {
  const { db, ingest } = fresh();
  ingest.handle({ type: "snapshot", slug: SLUG, ts: "2026-01-05T10:00:00.000Z", code: "a" });
  ingest.handle({ type: "session_end", slug: SLUG, ts: "2026-01-05T10:10:00.000Z", reason: "ended" });
  const s = session(db);
  db.prepare(
    `INSERT INTO attempts (session_id, slug, date, status, category, created_at) VALUES (?, ?, '2026-01-05', 'failed', 'x', 'now')`,
  ).run(s.id, SLUG);
  ingest.handle({ type: "judge", slug: SLUG, ts: "2026-01-05T10:05:00.000Z", data: acceptedSubmit });
  assert.equal(session(db).end_reason, "accepted");
  assert.equal((db.prepare(`SELECT COUNT(*) AS n FROM attempts`).get() as { n: number }).n, 1);
});

// ---- T-001: a result is recognised by its LeetCode submission id, per problem ----

const count = (db: DB, sql: string) => (db.prepare(sql).get() as { n: number }).n;

test("a repeated Accepted result after the session ended is stored once, in one session", () => {
  const { db, ingest } = fresh();
  ingest.handle({ type: "snapshot", slug: SLUG, ts: "2026-01-05T10:00:00.000Z", code: "a" });
  const first = ingest.handle({ type: "judge", slug: SLUG, ts: "2026-01-05T10:01:00.000Z", data: acceptedSubmit });
  const again = ingest.handle({ type: "judge", slug: SLUG, ts: "2026-01-05T10:01:01.000Z", data: acceptedSubmit });
  assert.equal(again.session_id, first.session_id);
  assert.equal(count(db, `SELECT COUNT(*) AS n FROM judge_events`), 1);
  assert.equal(count(db, `SELECT COUNT(*) AS n FROM sessions`), 1);
});

test("a repeated Run result after the session was ended does not open a new session", () => {
  const { db, ingest } = fresh();
  ingest.handle({ type: "snapshot", slug: SLUG, ts: "2026-01-05T10:00:00.000Z", code: "a" });
  ingest.handle({ type: "judge", slug: SLUG, ts: "2026-01-05T10:01:00.000Z", data: runResult });
  ingest.handle({ type: "session_end", slug: SLUG, ts: "2026-01-05T10:02:00.000Z", reason: "ended" });
  ingest.handle({ type: "judge", slug: SLUG, ts: "2026-01-05T10:05:00.000Z", data: runResult });
  assert.equal(count(db, `SELECT COUNT(*) AS n FROM sessions`), 1);
  assert.equal(count(db, `SELECT COUNT(*) AS n FROM judge_events`), 1);
});

test("a different submission for the same problem is still stored", () => {
  const { db, ingest } = fresh();
  const wrong = { ...acceptedSubmit, status_msg: "Wrong Answer", total_correct: 2, submission_id: "1234500" };
  ingest.handle({ type: "snapshot", slug: SLUG, ts: "2026-01-05T10:00:00.000Z", code: "a" });
  ingest.handle({ type: "judge", slug: SLUG, ts: "2026-01-05T10:01:00.000Z", data: wrong });
  ingest.handle({ type: "judge", slug: SLUG, ts: "2026-01-05T10:02:00.000Z", data: acceptedSubmit });
  const rows = db.prepare(`SELECT submission_id, status FROM judge_events ORDER BY ts`).all();
  assert.deepEqual(rows, [
    { submission_id: "1234500", status: "Wrong Answer" },
    { submission_id: "1234567", status: "Accepted" },
  ]);
});

test("the same submission id on a different problem is not treated as a repeat", () => {
  const { db, ingest } = fresh();
  ingest.handle({ type: "judge", slug: "problem-a", ts: "2026-01-05T10:01:00.000Z", data: runResult });
  ingest.handle({ type: "judge", slug: "problem-b", ts: "2026-01-05T10:01:00.000Z", data: runResult });
  assert.equal(count(db, `SELECT COUNT(*) AS n FROM judge_events`), 2);
});
