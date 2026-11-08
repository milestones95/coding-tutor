"""Judge-vs-human agreement (eval plan "Checking the judge"; rule 8; D-062). Tester-owned, deterministic.

Agreement is measured item by item: every (summary, item) pair the human graded counts once, and
an item the human marked not applicable (None) is skipped. Two numbers sit beside it, because a
calibration set where most items are met flatters a judge that always says yes:
  - `always_yes`: the agreement a judge answering "met" to everything would get;
  - `misses_caught`: of the items the human marked not met, how many the judge also marked not met.
"""


def agreement(human: list[dict], judge: list[dict]) -> dict:
    if len(human) != len(judge):
        raise ValueError("human and judge grade lists differ in length")
    pairs = [(h[i], j[i]) for h, j in zip(human, judge, strict=True) for i in h if h[i] is not None]
    if not pairs:
        raise ValueError("no graded items")
    agree = sum(h == j for h, j in pairs)
    misses = [(h, j) for h, j in pairs if h is False]
    return {"agreement": agree / len(pairs), "n": len(pairs),
            "always_yes": sum(h is True for h, _ in pairs) / len(pairs),
            "misses_caught": (sum(j is False for _, j in misses), len(misses))}


def by_item(human: list[dict], judge: list[dict]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = {}
    for h, j in zip(human, judge, strict=True):
        for i, v in h.items():
            if v is not None:
                a = out.setdefault(i, [0, 0])
                a[0] += v == j[i]
                a[1] += 1
    return {i: (a, n) for i, (a, n) in out.items()}
