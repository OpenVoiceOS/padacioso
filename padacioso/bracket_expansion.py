import re
from typing import Dict, List

from padacioso._bracket_expansion import expand_template, expand_slots


def expand_parentheses(sent: str) -> List[str]:
    """
    Expand a template string with ``(a|b)`` alternatives and ``[optional]``
    syntax into all possible combinations.

    Delegates to :func:`padacioso._bracket_expansion.expand_template` so that
    OVOS template semantics stay consistent across plugins.  Internal whitespace
    introduced by an empty ``[optional]`` branch is collapsed so that a single
    space separates tokens.

    Examples:
        "Will it (rain|pour) [today]?" ->
            ["Will it rain today?", "Will it rain?",
             "Will it pour today?", "Will it pour?"]
    """
    expansions = expand_template(sent)
    cleaned = {re.sub(r" +", " ", e).strip() for e in expansions}
    return sorted(cleaned)


def expand_template_slots(template: str,
                          slots: Dict[str, List[str]]) -> List[str]:
    """
    Expand ``(a|b)``/``[opt]`` template and substitute ``{slot}`` placeholders.

    Thin wrapper around :func:`padacioso._bracket_expansion.expand_slots` that
    additionally collapses any double whitespace introduced by empty optional
    branches.
    """
    expansions = expand_slots(template, slots)
    cleaned = {re.sub(r" +", " ", e).strip() for e in expansions}
    return sorted(cleaned)


def clean_braces(example: str) -> str:
    """
    Normalizes {{entity}} to {entity}
    @param example: utterance example to clean
    @return: cleaned example
    """
    clean = example.replace('{{', '{').replace('}}', '}')
    return clean


def translate_padatious(example: str) -> str:
    """
    Translate Padatious `:0` syntax to standard regex
    @param example: input intent example
    @return: parsed intent example with Padatious syntax replaced with regex
    """
    if ':0' not in example:
        return example
    tokens = example.split()
    i = 0
    for idx, token in enumerate(tokens):
        if token == ":0":
            tokens[idx] = '{' + f'word{i}:word' + '}'
            i += 1
    return " ".join(tokens)


def normalize_whitespace(text: str) -> str:
    """
    Collapse multiple consecutive whitespace characters into a single space
    and strip leading/trailing whitespace.
    @param text: input text
    @return: whitespace-normalized text
    """
    return re.sub(r'\s+', ' ', text).strip()


def drop_apostrophes(text: str) -> str:
    """
    Replace apostrophes and common apostrophe-like unicode variants with a space.
    Using a space rather than empty string preserves word boundaries so that
    "it's" -> "it s" and both sides of a match reduce the same way.
    @param text: input text
    @return: text with all apostrophe variants replaced by a space
    """
    apostrophe_variants = [
        "'",           # U+0027 ASCII apostrophe
        "’",      # U+2019 RIGHT SINGLE QUOTATION MARK
        "‘",      # U+2018 LEFT SINGLE QUOTATION MARK
        "ʼ",      # U+02BC MODIFIER LETTER APOSTROPHE
        "ʹ",      # U+02B9 MODIFIER LETTER PRIME
        "`",           # U+0060 GRAVE ACCENT (backtick)
        "´",      # U+00B4 ACUTE ACCENT
        "＇",      # U+FF07 FULLWIDTH APOSTROPHE
    ]
    for variant in apostrophe_variants:
        text = text.replace(variant, " ")
    return text


def _space_entities(text: str) -> str:
    """
    Ensure a space exists on both sides of every {entity} placeholder.
    Handles agglutinative suffixes like {keyword}ren so the suffix becomes
    a separate token and the capture group is not contaminated.
    """
    return re.sub(r'(\{[^}]+\})', r' \1 ', text)


def normalize_utterance(text: str) -> str:
    """
    Normalize a plain utterance (inference query) for consistent matching.
    Does NOT touch entity placeholder syntax.
    @param text: input utterance
    @return: normalized text
    """
    text = drop_apostrophes(text)
    text = normalize_whitespace(text)
    return text


def normalize_example(example: str) -> str:
    text = clean_braces(translate_padatious(example))
    text = drop_apostrophes(text)
    text = normalize_whitespace(text)
    return text
