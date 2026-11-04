# Capture fixtures (tester-owned)

LeetCode `/submissions/detail/<id>/check/` responses fed to the ingest server and the page hook
in tests. No fixture contains real account data. One fixture carries a `user` block of SENTINEL
values, so a test can prove profile data is never stored.

| File | Provenance | Used by |
|---|---|---|
| `run_check_success.json` | **Hand-built** 2026-11-02 by `/test write T-002`, from the field names the capture code reads (`judge.ts`) and the response shape seen in the human's DevTools. It is a Run (`runcode_` id, `RunCode` task), final poll, passing sample tests. | `tests/acceptance/test_t002_capture_move.py` |
| `submit_check_accepted.json` | **Transcribed** 2026-11-02 by `/test write T-001` from the human's DevTools screenshot of the final Submit poll `/submissions/detail/2188140749/v2/check/` (coin-change, Accepted 191/191). `compare_result` rebuilt as 191 × "1" (truncated on screen). | T-001 contract + acceptance |
| `submit_check_output_limit.json` | **Transcribed** 2026-11-02 from the human's screenshot of submission 2188175928 (Output Limit Exceeded, 68/191, `judger_status_code` 13). `compare_result` rebuilt as 68 × "1" + 123 × "0". | T-001 |
| `submit_check_wrong_answer.json` | **Hand-built** 2026-11-02 in the same shape (`status_code` 11). | T-001 |
| `submit_check_tle.json` | **Hand-built** 2026-11-02 in the same shape (`status_code` 14). | T-001 |
| `check_running.json` | **Transcribed** 2026-11-02 from the human's screenshot: a non-final poll, `{"state": "RUNNING_TESTS"}`. | T-001 |
| `check_pending.json` | **Hand-built** 2026-11-02: a non-final poll, `{"state": "PENDING"}`. | T-001 |
| `submit_check_with_user_block.json` | **Hand-built** 2026-11-02: the Accepted response plus a `user` block of SENTINEL values, used to prove no profile data is stored (T-001 Done-when 4). Not real account data. | T-001 |

