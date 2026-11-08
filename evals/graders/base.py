"""The grader interface (architecture §8.4). Tester-owned.

Every grader takes a case and the predictor's output and returns `Grade`s, so the runner treats
all metrics the same way. Deterministic graders and LLM judges are separate classes.
"""

from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel


class Grade(BaseModel):
    metric: str              # e.g. 'algorithm_overlap'
    value: float             # 0..1
    detail: str | None = None


class GradeContext(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    trajectory_path: Path | None = None   # agent suite
    client: Any = None                    # llm_judge graders only
    session: Any = None                   # the case's Session, for judges that read the timeline (D-062)


class Grader(Protocol):
    name: str
    version: str
    kind: Literal["deterministic", "llm_judge", "trajectory"]

    def grade(self, case: Any, output: dict, ctx: GradeContext) -> list[Grade]: ...
