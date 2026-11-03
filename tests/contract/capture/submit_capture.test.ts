// Contract tests for submit capture (T-001). Tester-owned (`/test write T-001`, 2026-11-02).
//
// The page hook is tested as shipped: `extension/page-hook.js` is loaded unchanged into a
// node:vm context whose `window` has stubbed fetch / monaco / postMessage (architecture §12).
// Responses are the recorded and hand-built LeetCode check/ payloads in evals/fixtures/capture/.
//
// Run: npm --prefix ux-extension run test:contract
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { normalizeJudge } from "../../../ux-extension/server/src/judge.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const HOOK_SRC = fs.readFileSync(path.join(REPO, "ux-extension/extension/page-hook.js"), "utf8");
const FIX = path.join(REPO, "evals/fixtures/capture");
const fixture = (name: string): Record<string, any> => JSON.parse(fs.readFileSync(path.join(FIX, name), "utf8"));

const RUN_URL = "https://leetcode.com/submissions/detail/runcode_1793660300.5534081_T002probe/check/";
const submitUrl = (id: string) => `https://leetcode.com/submissions/detail/${id}/v2/check/`;
const SUBMIT_FIXTURES = [
  "submit_check_accepted.json",
  "submit_check_wrong_answer.json",
  "submit_check_tle.json",
  "submit_check_output_limit.json",
];
const CODE = "class Solution:\n    def coinChange(self, coins, amount):\n        return -1\n";

type Posted = { source: string; type: string; payload: any };

function workingMonaco() {
  const model = { getValue: () => CODE, getLanguageId: () => "python3", getValueLength: () => CODE.length };
  return { editor: { getEditors: () => [{ getModel: () => model }], getModels: () => [model] } };
}

function throwingMonaco() {
  const boom = () => {
    throw new Error("Illegal value for lineNumber");
  };
  return { editor: { getEditors: boom, getModels: boom } };
}

/** Load page-hook.js into a fresh fake page. `routes` maps a URL to the JSON body fetch returns. */
function loadHook(routes: Record<string, unknown>, monaco: unknown = workingMonaco()) {
  const posted: Posted[] = [];
  const fetchStub = async (input: any) => {
    const url = typeof input === "string" ? input : input.url;
    if (!(url in routes)) throw new Error(`test has no route for ${url}`);
    return new Response(JSON.stringify(routes[url]), { headers: { "content-type": "application/json" } });
  };
  const win: any = {
    location: { origin: "https://leetcode.com", pathname: "/problems/coin-change/description/" },
    postMessage: (msg: Posted) => posted.push(JSON.parse(JSON.stringify(msg))),
    fetch: fetchStub,
    monaco,
    document: { querySelectorAll: () => [] },
    console: { debug() {}, warn() {}, log() {}, error() {} },
    setInterval: () => 0, // no snapshot polling in these tests
    Response,
    Request,
  };
  win.window = win;
  vm.createContext(win);
  vm.runInContext(HOOK_SRC, win, { filename: "page-hook.js" });
  const judges = () => posted.filter((m) => m.type === "judge");
  return { win, posted, judges };
}

const settle = () => new Promise((r) => setTimeout(r, 25));

// ---------------------------------------------------------------- page hook

test("a Run's final poll (/check/) posts one judge message", async () => {
  const run = fixture("run_check_success.json");
  const { win, judges } = loadHook({ [RUN_URL]: run });
  await win.window.fetch(RUN_URL);
  await settle();
  assert.equal(judges().length, 1);
  assert.equal(judges()[0].payload.url, RUN_URL);
  assert.deepEqual(judges()[0].payload.data, run);
  assert.equal(judges()[0].payload.code, CODE);
});

for (const name of SUBMIT_FIXTURES) {
  test(`a Submit's final poll (/v2/check/) posts one judge message — ${name}`, async () => {
    const data = fixture(name);
    const url = submitUrl(data.submission_id);
    const { win, judges } = loadHook({ [url]: data });
    await win.window.fetch(url);
    await settle();
    assert.equal(judges().length, 1, "the hook ignored a Submit result (T-001 finding: /v2/ segment)");
    assert.equal(judges()[0].payload.url, url);
    assert.deepEqual(judges()[0].payload.data, data);
  });
}

test("a Submit poll requested with a Request object is also captured", async () => {
  const data = fixture("submit_check_accepted.json");
  const url = submitUrl(data.submission_id);
  const { win, judges } = loadHook({ [url]: data });
  await win.window.fetch(new Request(url));
  await settle();
  assert.equal(judges().length, 1);
});

for (const name of ["check_running.json", "check_pending.json"]) {
  test(`a non-final poll posts nothing — ${name}`, async () => {
    const pending = fixture(name);
    const sUrl = submitUrl("2188140749");
    const { win, judges } = loadHook({ [RUN_URL]: pending, [sUrl]: pending });
    await win.window.fetch(RUN_URL);
    await win.window.fetch(sUrl);
    await settle();
    assert.equal(judges().length, 0);
  });
}

test("a full Submit sequence (pending, running, final) posts exactly one judge message", async () => {
  const final = fixture("submit_check_accepted.json");
  const url = submitUrl(final.submission_id);
  const bodies = [fixture("check_pending.json"), fixture("check_running.json"), final];
  let i = 0;
  // Each call to this URL returns the next poll body, as LeetCode's polling does.
  const routes = new Proxy({} as Record<string, unknown>, {
    has: (_t, key) => key === url,
    get: (_t, key) => (key === url ? bodies[Math.min(i++, bodies.length - 1)] : undefined),
  });
  const { win, judges } = loadHook(routes);
  for (let n = 0; n < bodies.length; n++) await win.window.fetch(url);
  await settle();
  assert.equal(judges().length, 1);
  assert.equal(judges()[0].payload.data.status_msg, "Accepted");
});

test("unrelated requests post nothing", async () => {
  const { win, judges } = loadHook({ "https://leetcode.com/graphql/": { data: {} } });
  await win.window.fetch("https://leetcode.com/graphql/");
  await settle();
  assert.equal(judges().length, 0);
});

test("the page still receives LeetCode's response unchanged", async () => {
  const data = fixture("submit_check_accepted.json");
  const url = submitUrl(data.submission_id);
  const { win } = loadHook({ [url]: data });
  const res = await win.window.fetch(url);
  assert.deepEqual(await res.json(), data);
});

test("the result is still posted when reading the editor fails (code is null)", async () => {
  // Uses a Run URL, which the hook already matches, so this isolates the editor-failure rule
  // from the /v2/ URL bug.
  const data = fixture("run_check_success.json");
  const { win, judges } = loadHook({ [RUN_URL]: data }, throwingMonaco());
  await win.window.fetch(RUN_URL);
  await settle();
  assert.equal(judges().length, 1, "an editor error must not drop the judge result");
  assert.equal(judges()[0].payload.code, null);
  assert.deepEqual(judges()[0].payload.data, data);
});

// ---------------------------------------------------------------- judge.ts

const EXPECTED: Record<string, { status: string; passed: number; total: number; failed: boolean }> = {
  "submit_check_accepted.json": { status: "Accepted", passed: 191, total: 191, failed: false },
  "submit_check_wrong_answer.json": { status: "Wrong Answer", passed: 40, total: 191, failed: true },
  "submit_check_tle.json": { status: "Time Limit Exceeded", passed: 120, total: 191, failed: true },
  "submit_check_output_limit.json": { status: "Output Limit Exceeded", passed: 68, total: 191, failed: true },
};

for (const [name, exp] of Object.entries(EXPECTED)) {
  test(`normalizeJudge: Submit response → submit row fields — ${name}`, () => {
    const data = fixture(name);
    const j = normalizeJudge(data, submitUrl(data.submission_id));
    assert.equal(j.kind, "submit");
    assert.equal(j.submission_id, data.submission_id);
    assert.match(j.submission_id ?? "", /^\d+$/);
    assert.equal(j.status, exp.status, "status is LeetCode's verdict text, verbatim");
    assert.equal(j.tests_passed, exp.passed);
    assert.equal(j.tests_total, exp.total);
    if (exp.failed) assert.ok(j.error_detail, "a failed submit carries error_detail");
    else assert.equal(j.error_detail, null);
  });
}

test("normalizeJudge: OLE error_detail carries the failing input and expected output", () => {
  const data = fixture("submit_check_output_limit.json");
  const j = normalizeJudge(data, submitUrl(data.submission_id));
  assert.ok(j.error_detail?.includes("[271,5,343,254,112]"));
  assert.ok(j.error_detail?.includes("17"));
});

test("normalizeJudge: submission_id falls back to the id in a /v2/check/ URL", () => {
  const { submission_id, ...data } = fixture("submit_check_accepted.json");
  const j = normalizeJudge(data, submitUrl(submission_id));
  assert.equal(j.submission_id, submission_id);
  assert.equal(j.kind, "submit");
});

test("normalizeJudge: a Run stays a run", () => {
  assert.equal(normalizeJudge(fixture("run_check_success.json"), RUN_URL).kind, "run");
});

test("normalizeJudge: no LeetCode user profile data in the output", () => {
  const data = fixture("submit_check_with_user_block.json");
  const out = JSON.stringify(normalizeJudge(data, submitUrl(data.submission_id)));
  assert.ok(!out.includes("SENTINEL"), "user block leaked into the normalized judge event");
});
