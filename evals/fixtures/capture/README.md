# Capture fixtures (tester-owned)

LeetCode `/submissions/detail/<id>/check/` responses fed to the ingest server and the page hook
in tests. No fixture contains LeetCode's `user` block or any account data.

| File | Provenance | Used by |
|---|---|---|
| `run_check_success.json` | **Hand-built** 2026-11-02 by `/test write T-002`, from the field names the capture code reads (`judge.ts`) and the response shape seen in the human's DevTools. It is a Run (`runcode_` id, `RunCode` task), final poll, passing sample tests. | `tests/acceptance/test_t002_capture_move.py` |

Recorded responses for Submit (`/v2/check/`) come with `/test write T-001`.
