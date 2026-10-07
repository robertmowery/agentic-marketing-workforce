"""How far to trust a judge: the same drafts, scored repeatedly.

Four fixed drafts, one clean and three each broken in one known way, are put
in front of the brand reviewer several times. A second checker written in
plain code looks for the two faults that code can see without help.
"""

from __future__ import annotations

HYPE_WORDS = ("revolutionary", "game-changing", "world-class", "unbeatable", "best-in-class")

_CLEAN_EMAIL = (
    "Subject: Secure every truck in your fleet with one key. "
    "Theft from open racks and gear damage cost your crews time. TrailLock 2 offers"
    " keyed-alike locking across up to 500 vehicles and installs in 20 minutes with"
    " no drilling. It carries a 5-year warranty. Book a 20-minute demo this quarter."
)

# name -> (draft text, the fault planted in it or None)
DRAFTS: dict[str, tuple[str, str | None]] = {
    "clean": (_CLEAN_EMAIL, None),
    "hype": (
        _CLEAN_EMAIL.replace(
            "TrailLock 2 offers", "The revolutionary, game-changing TrailLock 2 offers"
        ),
        "hype words",
    ),
    "unapproved_claim": (
        _CLEAN_EMAIL.replace("5-year warranty", "10-year warranty and is fully waterproof"),
        "claims that are not approved facts",
    ),
    "no_call_to_action": (
        _CLEAN_EMAIL.replace(" Book a 20-minute demo this quarter.", ""),
        "no call to action",
    ),
}


def judge_request(draft: str) -> str:
    """Wrap a draft in everything the judge needs to apply its rubric."""
    return f"Audience: fleet managers at regional utility companies.\n\nDraft to review: {draft}"


def code_check(draft: str) -> dict[str, bool]:
    """Check the two faults that need no judgment: banned words and an invented number.

    Returns:
        ``passed`` plus one flag per rule. This cannot tell whether a draft
        speaks to the reader or has a clear call to action. That takes a judge.
    """
    lowered = draft.lower()
    no_hype = not any(word in lowered for word in HYPE_WORDS)
    # The only warranty the company approved is five years.
    warranty_as_approved = "warranty" not in lowered or "5-year warranty" in lowered
    no_unapproved_feature = "waterproof" not in lowered
    passed = no_hype and warranty_as_approved and no_unapproved_feature
    return {
        "passed": passed,
        "no_hype_words": no_hype,
        "warranty_as_approved": warranty_as_approved,
        "no_unapproved_feature": no_unapproved_feature,
    }
