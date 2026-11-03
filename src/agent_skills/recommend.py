"""Deterministic, explainable skill recommendations."""

import re
from pathlib import Path


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


def _estimate_skill_tokens(record, _cache={}):
    """Rough token estimate for a skill: read SKILL.md (bounded), chars // 4.

    Results are cached by real_path so repeated calls (apply/plan/launch)
    do not re-read the file on every invocation.
    """
    real_path = record.get("real_path") or ""
    if real_path in _cache:
        return _cache[real_path]
    skill_md = Path(real_path) / "SKILL.md"
    try:
        with skill_md.open("r", encoding="utf-8", errors="replace") as f:
            text = f.read(65536)
        est = max(1, len(text) // 4)
    except OSError:
        est = 1024
    _cache[real_path] = est
    return est


def filter_skills_for_context(records, selected_ids, technologies,
                              budget_tokens, max_skills,
                              existing_instructions_text=""):
    """
    Filter skill records to only those in selected_ids, score them, sort by
    relevance, and truncate to fit the token budget and max skills cap.

    Returns:
        filtered_records: list of skill record dicts that fit in context
        skipped_count: number of selected skills excluded
        total_estimated_tokens: estimated tokens of filtered records
        warnings: list of warning strings
    """
    selected_set = set(selected_ids or [])
    candidates = [r for r in records if r.get("dir_name") in selected_set]

    # Score each candidate.
    scored = []
    for r in candidates:
        s, reasons = score_skill(r, technologies, existing_instructions_text)
        scored.append((r, s, reasons))

    # Sort by score desc, then dir_name asc (deterministic).
    scored.sort(key=lambda x: (-x[1], x[0].get("dir_name", "")))

    # Hard cap on number of skills. max_skills <= 0 means unlimited.
    if max_skills is not None and max_skills > 0 and len(scored) > max_skills:
        scored = scored[:max_skills]

    # Truncate to token budget. budget_tokens <= 0 means unlimited.
    filtered = []
    total_tokens = 0
    budget_unlimited = budget_tokens is None or budget_tokens <= 0
    for r, s, reasons in scored:
        if budget_unlimited:
            filtered.append(r)
            continue
        est_tokens = _estimate_skill_tokens(r)
        if total_tokens + est_tokens > budget_tokens:
            break
        filtered.append(r)
        total_tokens += est_tokens

    # Only skills actually considered (candidates) and cut by budget/max_skills
    # count as budget exclusions; undiscovered/nonexistent selected skills do not.
    skipped = len(candidates) - len(filtered)
    warnings = []
    if skipped > 0:
        warnings.append(
            "context budget: %d selected skill(s) excluded "
            "(budget=%d tokens, max=%d skills)" %
            (skipped, budget_tokens if budget_tokens is not None else 0, max_skills if max_skills is not None else 0)
        )

    return filtered, skipped, total_tokens, warnings