"""Padacioso bracket expansion utilities.

The expansion core (``(a|b)`` alternatives, ``[optional]`` syntax) now lives
in :mod:`ovos_spec_tools` and is shared with every OVOS intent engine. The
symbols in this module are thin shims that delegate to it while preserving
padacioso's legacy quirks:

* slot syntax ``{name:type}`` — supported here but not in OVOS-INTENT-1; the
  shim mangles colons before calling :func:`ovos_spec_tools.expand` and
  restores them in the output.
* the sorted, deduplicated return list shape that the test suite expects.

Padacioso-specific normalization helpers (``drop_apostrophes``,
``translate_padatious``, ``clean_braces``, ``_space_entities``, …) live
on; they sit *outside* the expansion math and stay local because they
encode engine-specific matching policy.
"""
import re
import warnings

from ovos_spec_tools import expand as _spec_expand
from ovos_utils.log import deprecated

from padacioso.version import VERSION_MAJOR

_REMOVAL_VERSION = f"{VERSION_MAJOR + 1}.0.0"

# Encode "{name:type}" → "{name__COLON__type}" so ovos-spec-tools accepts the
# slot name; reverse on the way out so callers still see the padacioso form.
_SLOT_RE = re.compile(r"\{([^{}]+)\}")
_MANGLE_TOKEN = "padslot"
_UNMANGLE_RE = re.compile(rf"\{{{_MANGLE_TOKEN}(\d+)\}}")
# Single-branch groups like `(word)` are valid padacioso input but rejected
# by OVOS-INTENT-1; strip the parens before expanding.
_SINGLE_BRANCH_GROUP_RE = re.compile(r"\(([^()|]+)\)")


def _mangle(text: str):
    """Replace every {…} slot with a spec-compliant placeholder.

    Returns (mangled_text, list_of_original_slot_bodies). The slot body
    (whatever is between the braces, e.g. ``foo:int`` or ``Foo``) is
    preserved verbatim so we can restore it after expansion.
    """
    originals = []

    def _sub(m):
        originals.append(m.group(1))
        return "{" + _MANGLE_TOKEN + str(len(originals) - 1) + "}"

    return _SLOT_RE.sub(_sub, text), originals


def _unmangle(text: str, originals) -> str:
    return _UNMANGLE_RE.sub(lambda m: "{" + originals[int(m.group(1))] + "}", text)


@deprecated(
    "padacioso.bracket_expansion.expand_parentheses is deprecated; "
    "use ovos_spec_tools.expand instead",
    _REMOVAL_VERSION,
)
def expand_parentheses(sent: str) -> list:
    """Expand a template with ``(a|b)`` and ``[optional]`` syntax.

    Delegates the expansion math to :func:`ovos_spec_tools.expand`. The
    return is sorted and deduplicated to preserve padacioso's historical
    output shape.
    """
    warnings.warn(
        "padacioso.bracket_expansion.expand_parentheses is deprecated; "
        "use ovos_spec_tools.expand instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return _expand_parentheses_impl(sent)


def _expand_parentheses_impl(sent: str) -> list:
    if not sent:
        return [sent]
    # Collapse single-branch groups so OVOS-INTENT-1 accepts the template.
    prepared = sent
    while True:
        new = _SINGLE_BRANCH_GROUP_RE.sub(r"\1", prepared)
        if new == prepared:
            break
        prepared = new
    mangled, originals = _mangle(prepared)
    # OVOS-INTENT-1 §3.6 forbids adjacent slots; insert a sentinel literal
    # between any two slots so spec-tools accepts the template, then strip
    # the sentinel from each emitted sample.
    sentinel = "padsep"
    spaced = re.sub(
        rf"(\{{{_MANGLE_TOKEN}\d+\}})(\s+)(\{{{_MANGLE_TOKEN}\d+\}})",
        rf"\1 {sentinel} \3",
        mangled,
    )
    # the substitution only catches one pair at a time; loop until stable
    while True:
        again = re.sub(
            rf"(\{{{_MANGLE_TOKEN}\d+\}})(\s+)(\{{{_MANGLE_TOKEN}\d+\}})",
            rf"\1 {sentinel} \3",
            spaced,
        )
        if again == spaced:
            break
        spaced = again
    samples = _spec_expand(spaced)
    cleaned = set()
    for s in samples:
        s = re.sub(rf"\s+{sentinel}\s+", " ", s)
        cleaned.add(_unmangle(s, originals))
    return sorted(cleaned)


def clean_braces(example: str) -> str:
    """Normalize ``{{entity}}`` to ``{entity}``."""
    return example.replace('{{', '{').replace('}}', '}')


def translate_padatious(example: str) -> str:
    """Translate Padatious ``:0`` syntax to padacioso slot syntax."""
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
    """Collapse repeated whitespace and strip."""
    return re.sub(r'\s+', ' ', text).strip()


def drop_apostrophes(text: str) -> str:
    """Replace ASCII and unicode apostrophe variants with a space.

    Using a space preserves word boundaries so ``it's`` -> ``it s`` and both
    sides of a match reduce the same way.
    """
    apostrophe_variants = [
        "'",           # U+0027 ASCII apostrophe
        "’",      # U+2019 RIGHT SINGLE QUOTATION MARK
        "‘",      # U+2018 LEFT SINGLE QUOTATION MARK
        "ʼ",      # U+02BC MODIFIER LETTER APOSTROPHE
        "ʹ",      # U+02B9 MODIFIER LETTER PRIME
        "`",           # U+0060 GRAVE ACCENT
        "´",      # U+00B4 ACUTE ACCENT
        "＇",      # U+FF07 FULLWIDTH APOSTROPHE
    ]
    for variant in apostrophe_variants:
        text = text.replace(variant, " ")
    return text


def _space_entities(text: str) -> str:
    """Ensure space around every ``{entity}`` placeholder."""
    return re.sub(r'(\{[^}]+\})', r' \1 ', text)


def normalize_utterance(text: str) -> str:
    """Normalize an inference query (does not touch slot placeholders)."""
    text = drop_apostrophes(text)
    text = normalize_whitespace(text)
    return text


def normalize_example(example: str) -> str:
    text = clean_braces(translate_padatious(example))
    text = drop_apostrophes(text)
    text = normalize_whitespace(text)
    return text
