"""Prompts. Grounding is value-blind: it names what to look for, never the target values.

Judges (the baselines) receive the objective and every requirement in plain words, which
is the same information the rule engine of EduAssetVerify receives as the constraint set.
"""
from __future__ import annotations

from ..evidence import COUNT_VOCAB, SHAPE_VOCAB

BOX = '{"left": int, "top": int, "right": int, "bottom": int}'
COORDS = ("Coordinates are integers from 0 to 1000: 0 is the left or top edge of the image, "
          "1000 the right or bottom edge.")


def _vocab(words: list[str], order: list[int] | None) -> str:
    words = list(words) if order is None else [words[i] for i in order]
    return ", ".join(words)


def grounding(schema: str, vocab_order: list[int] | None = None) -> str:
    head = ("You are looking at a picture made for an educational game. Describe what the picture shows "
            "as JSON. Report only what you see; do not judge whether the picture is correct.\n\n")
    if schema == "partition":
        return head + (
            '{"shapes": [{"shape": "circle" | "rectangle" | "other", "box": ' + BOX + ',\n'
            '             "parts": [{"box": ' + BOX + ', "colored": true | false}]}],\n'
            ' "texts": [{"text": "exact characters", "box": ' + BOX + '}]}\n\n'
            f"- {COORDS}\n"
            "- A shape may be divided into parts by lines. List every part of every shape separately.\n"
            '- "colored" is true when a part is filled with a color that differs from the unfilled parts.\n'
            "- List every piece of text exactly as written, for example digits or fractions such as 3/8.")
    if schema == "counting":
        return head + (
            '{"objects": [{"category": "<one of: ' + _vocab(COUNT_VOCAB, vocab_order) + '>", "box": ' + BOX + '}],\n'
            ' "texts": [{"text": "exact characters", "box": ' + BOX + '}],\n'
            ' "lines": [{"style": "solid" | "dashed", "orientation": "vertical" | "horizontal", '
            '"position": int}]}\n\n'
            f"- {COORDS} A line's position is its x (vertical line) or y (horizontal line).\n"
            "- List every object separately, also when several objects look alike.\n"
            "- List every piece of text exactly as written.")
    return head + (
        '{"objects": [{"category": "<one of: ' + _vocab(SHAPE_VOCAB, vocab_order) + '>", "box": ' + BOX + ',\n'
        '              "direction": "up" | "down" | "left" | "right" | "none"}],\n'
        ' "lines": [{"style": "solid" | "dashed", "orientation": "vertical" | "horizontal", '
        '"position": int}]}\n\n'
        f"- {COORDS} A line's position is its x (vertical line) or y (horizontal line).\n"
        "- List every object separately.\n"
        '- For an arrow, "direction" is where its tip points; for any other object use "none".')


def read_text() -> str:
    return ('This crop is taken from a picture for an educational game. Read the text in it exactly, '
            'character by character (digits, "/", letters). Return JSON {"text": "..."}; use "" if there is no text.')


def read_tiles(n: int, vocab: list[str]) -> str:
    return (f"This image is a grid of {n} numbered tiles; each tile shows one object cut out of a picture. "
            f"Name the object in each tile with one word from: {', '.join(vocab)}. "
            'Return JSON {"tiles": [{"tile": 1, "category": "..."}, ...]} with one entry per tile.')


def _requirements(constraints: list[dict], order: list[int] | None = None) -> str:
    idx = list(range(len(constraints))) if order is None else order
    return "\n".join(f"{k + 1}. {constraints[i]['text']}" for k, i in enumerate(idx))


def _context(objective: str, constraints: list[dict], order) -> str:
    return (f'This picture was generated for an educational game. Learning objective: "{objective}"\n'
            f"A correct picture satisfies every requirement:\n{_requirements(constraints, order)}\n\n")


def _options(swap: bool) -> str:
    return '"INVALID" or "VALID"' if swap else '"VALID" or "INVALID"'


def judge_direct(objective, constraints, order=None, swap=False) -> str:
    return (_context(objective, constraints, order) +
            f'Is the picture a correct educational asset for this objective? Return JSON {{"verdict": {_options(swap)}}}.')


def judge_cot(objective, constraints, order=None, swap=False) -> str:
    return (_context(objective, constraints, order) +
            "Think step by step: describe what you see, check each requirement against the picture, then decide. "
            f'Return JSON {{"reasoning": "...", "verdict": {_options(swap)}}}.')


def judge_structured(objective, constraints, order=None, swap=False) -> str:
    return (_context(objective, constraints, order) +
            "Check each requirement against the picture. "
            'Return JSON {"requirements": [{"number": 1, "satisfied": true | false}, ...], '
            f'"verdict": {_options(swap)}}} with one entry per requirement, in the order listed.')
