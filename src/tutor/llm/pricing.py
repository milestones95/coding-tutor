"""Token prices from `config/pricing.toml` (architecture §6.5, §11).

Cost is computed here, the same way for every provider (D-008), so the model comparison's cost
column can't drift between adapters. A model with no entry is an `LLMConfigError`: a call
whose cost can't be recorded isn't allowed to run.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from tutor.config import REPO_ROOT
from tutor.llm.errors import LLMConfigError

DEFAULT_PRICING = REPO_ROOT / "config" / "pricing.toml"


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float
    as_of: str

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok) / 1_000_000


def load_pricing(path: Path) -> dict[str, Price]:
    """`{"provider:model": Price}` from a pricing file."""
    try:
        raw = tomllib.loads(Path(path).read_text())
    except FileNotFoundError:
        raise LLMConfigError(f"pricing file not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise LLMConfigError(f"{path}: not valid TOML ({e})") from None
    prices = {}
    for ref, entry in (raw.get("models") or {}).items():
        try:
            prices[ref] = Price(float(entry["input_per_mtok"]), float(entry["output_per_mtok"]), str(entry["as_of"]))
        except (KeyError, TypeError, ValueError):
            raise LLMConfigError(f"{path}: [models.\"{ref}\"] needs input_per_mtok, output_per_mtok and as_of") from None
    return prices


def price_for(path: Path, ref: str) -> Price:
    prices = load_pricing(path)
    if ref not in prices:
        raise LLMConfigError(f"no price for {ref} in {path}; add [models.\"{ref}\"] before using it")
    return prices[ref]
