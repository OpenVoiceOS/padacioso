"""Inline OVOS template-syntax expansion helpers.

Local implementation of ``expand_template`` and ``expand_slots`` so the plugin
does not need a runtime dependency on ``ovos-utils`` just for two regexes.
Mirrors the semantics of ``ovos_utils.bracket_expansion``.
"""
import itertools
import re
from typing import Dict, List


def expand_template(template: str) -> List[str]:
    """Expand ``(a|b)`` alternatives and ``[opt]`` optionals into concrete sentences."""

    def expand_optional(text: str) -> str:
        return re.sub(r"\[([^\[\]]+)\]", lambda m: f"({m.group(1)}|)", text)

    def expand_alternatives(text: str):
        parts = []
        for segment in re.split(r"(\([^\(\)]+\))", text):
            if segment.startswith("(") and segment.endswith(")"):
                parts.append(segment[1:-1].split("|"))
            else:
                parts.append([segment])
        return itertools.product(*parts)

    def fully_expand(texts):
        result = set(texts)
        while True:
            expanded = set()
            for text in result:
                for option in expand_alternatives(text):
                    expanded.add("".join(option).strip())
            if expanded == result:
                break
            result = expanded
        return sorted(result)

    return fully_expand([expand_optional(template)])


def expand_slots(template: str, slots: Dict[str, List[str]]) -> List[str]:
    """``expand_template`` then substitute ``{slot}`` placeholders from *slots*."""
    base = expand_template(template)
    out: List[str] = []
    for sentence in base:
        matches = re.findall(r"\{([^\{\}]+)\}", sentence)
        if not matches:
            out.append(sentence)
            continue
        slot_options = [slots.get(m, [f"{{{m}}}"]) for m in matches]
        for combo in itertools.product(*slot_options):
            filled = sentence
            for s, v in zip(matches, combo):
                filled = filled.replace(f"{{{s}}}", v)
            out.append(filled)
    return out
