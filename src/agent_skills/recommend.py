"""Deterministic, explainable skill recommendations."""

import re


def _tokens(text):
    if not text:
        return []
    return re.findall(r"[A-Za-z0-9]+", text.lower())


def score_skill(record, technologies, existing_instructions_text=""):
    """Return (score, reasons_list) for a skill record."""
    score = 0
    reasons = []
    tech_names = [t["name"] if isinstance(t, dict) else str(t) for t in (technologies or [])]
    tech_set = set(tech_names)

    dir_name = record.get("dir_name") or ""
    declared = record.get("declared_name") or ""
    desc = record.get("description") or ""
    haystack = " ".join([dir_name, declared, desc]).lower()
    tokens = set(_tokens(haystack))

    # Technology direct match.
    for tech in tech_names:
        t = tech.lower()
        if t and t in haystack:
            score += 5
            reasons.append("technology match: %s" % tech)
    # Keyword overlap with tech names.
    for tech in tech_names:
        for tok in _tokens(tech):
            if tok in tokens and len(tok) > 2:
                score += 1
    # Existing instructions text.
    if existing_instructions_text:
        inst_tokens = set(_tokens(existing_instructions_text))
        overlap = inst_tokens & tokens
        if overlap:
            score += min(3, len(overlap))
            reasons.append("instruction keyword overlap: %s" % ", ".join(sorted(list(overlap))[:5]))

    if score <= 0:
        score = 0
    return score, reasons


def recommend(records, technologies, limit=20, existing_instructions_text="", all_results=False):
    scored = []
    for r in records:
        s, reasons = score_skill(r, technologies, existing_instructions_text)
        if s > 0 or all_results:
            scored.append({"record": r, "score": s, "reasons": reasons if reasons else ["no strong signal"]})
    scored.sort(key=lambda x: (-x["score"], x["record"].get("dir_name", "")))
    if not all_results:
        scored = scored[:limit]
    return scored