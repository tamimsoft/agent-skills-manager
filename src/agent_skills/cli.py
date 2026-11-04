"""CLI for the agent skill manager."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from agent_skills import __version__
from agent_skills.agents_md import generate_agents_md, extract_agents_block
from agent_skills.config import load_config, resolve_library_root, default_config
from agent_skills.discovery import discover_skills, DiscoveryError
from agent_skills.manifest import (
    manifest_path, load_manifest, save_manifest, default_manifest, selected_ids,
    validate_manifest, agent_is_enabled,
)
from agent_skills.project import find_project_root
from agent_skills.detection import detect_technologies
from agent_skills.recommend import recommend, filter_skills_for_context
from agent_skills.links import OWNED_RULES_FILENAME, read_marker
from agent_skills.adapter_common import build_skill_entry, build_skills_dir_atomic
from agent_skills.lock import AdvisoryLock, LockError
from agent_skills import identity
from agent_skills.resolution import resolve_resolutions, resolution_summary

SUPPORTED_AGENTS = (
    ("opencode", "OpenCode"),
    ("junie", "Junie"),
    ("kilo", "Kilo"),
)


def _build_parser():
    parser = argparse.ArgumentParser(prog="agent-skills", description="Global agent skill manager")
    parser.add_argument("--version", action="version", version="agent-skills %s" % __version__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--no-cache", action="store_true", help="bypass discovery cache")
    confirm_flags = argparse.ArgumentParser(add_help=False)
    confirm_flags.add_argument("--yes", action="store_true", help="accept confirmations")
    confirm_flags.add_argument("--dry-run", action="store_true", help="show changes, change nothing")
    dry_run_flags = argparse.ArgumentParser(add_help=False)
    dry_run_flags.add_argument("--dry-run", action="store_true", help="show changes, change nothing")

    sub = parser.add_subparsers(dest="command")

    # list
    p = sub.add_parser("list", help="list library skills")
    p.add_argument("--selected", action="store_true")
    p.add_argument("--filter", default="")
    p.add_argument("--tech", default="")
    p.add_argument("--json", action="store_true", dest="json_out")
    p.add_argument("--no-cache", action="store_true", dest="no_cache")

    # init
    p = sub.add_parser("init", help="initialize project; use --interactive for guided setup", parents=[confirm_flags])
    p.add_argument("--name", default=None)
    p.add_argument("--interactive", action="store_true", help="choose agent targets and skills after detection")

    # select
    p = sub.add_parser("select", help="interactively select skills from recommendations", parents=[confirm_flags])
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--all", action="store_true")
    p.add_argument("--filter", default="")
    p.add_argument("--tech", default="")

    # add
    p = sub.add_parser("add", help="add skills by dir_name", parents=[confirm_flags])
    p.add_argument("skills", nargs="+")

    # remove
    p = sub.add_parser("remove", help="remove skills from manifest", parents=[confirm_flags])
    p.add_argument("skills", nargs="+")

    # detect
    sub.add_parser("detect", help="show detected technologies")

    # recommend
    p = sub.add_parser("recommend", help="show scored recommendations")
    p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int, default=20)

    # validate
    sub.add_parser("validate", help="validate config, manifest, library")

    # sync
    p = sub.add_parser("sync", help="regenerate generated state from manifest", parents=[dry_run_flags])

    # doctor
    sub.add_parser("doctor", help="environment checks")

    # clean
    p = sub.add_parser("clean", help="remove orphaned generated directories", parents=[confirm_flags])

    # junie
    p = sub.add_parser("junie", help="launch Junie with managed skills", parents=[dry_run_flags])
    p.add_argument("--prepare", action="store_true")
    p.add_argument("args", nargs=argparse.REMAINDER)

    # kilo
    p = sub.add_parser("kilo", help="Kilo subcommands")
    sp = p.add_subparsers(dest="kilo_sub")
    for name in ("plan", "apply", "validate", "run"):
        parents = [confirm_flags] if name in ("apply", "run") else []
        subp = sp.add_parser(name, help="%s Kilo config" % name, parents=parents)
        subp.add_argument("args", nargs=argparse.REMAINDER)

    # opencode
    p = sub.add_parser("opencode", help="OpenCode subcommands")
    sp = p.add_subparsers(dest="oc_sub")
    for name in ("plan", "apply", "validate", "run"):
        parents = [confirm_flags] if name == "apply" else [dry_run_flags] if name == "run" else []
        subp = sp.add_parser(name, help="%s OpenCode config" % name, parents=parents)
        subp.add_argument("args", nargs=argparse.REMAINDER)

    return parser


def _is_tty():
    return sys.stdin.isatty()


def _confirm(prompt, yes):
    if yes:
        return True
    if not _is_tty():
        return False
    try:
        ans = input(prompt + " [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def _configured_agent_command(cfg, agent_id):
    paths = cfg.get("agent_paths", {}) if isinstance(cfg, dict) else {}
    configured = paths.get(agent_id) if isinstance(paths, dict) else None
    return configured if isinstance(configured, str) and configured else agent_id


def _agent_availability(cfg, agent_id):
    command = _configured_agent_command(cfg, agent_id)
    return shutil.which(command)


def interactive_select_agents(cfg, initial_selected=None):
    """Toggle supported managed agents; return None if cancelled."""
    chosen = set(initial_selected or ())
    while True:
        print("\nSupported agent targets (toggle numbers, Enter to confirm, 'q' to cancel):")
        for index, (agent_id, label) in enumerate(SUPPORTED_AGENTS, 1):
            executable = _agent_availability(cfg, agent_id)
            availability = "available: %s" % executable if executable else (
                "not found: %s" % _configured_agent_command(cfg, agent_id)
            )
            mark = "x" if agent_id in chosen else " "
            print("  [%s] %d. %-10s %s" % (mark, index, label, availability))
        try:
            raw = input("> ").strip()
        except EOFError:
            return None
        if raw.lower() in ("", "done", "ok"):
            return [agent_id for agent_id, _ in SUPPORTED_AGENTS if agent_id in chosen]
        if raw.lower() == "q":
            return None
        for token in raw.split():
            try:
                index = int(token)
            except ValueError:
                print("Enter one or more listed numbers, Enter to finish, or 'q' to cancel.")
                break
            if 1 <= index <= len(SUPPORTED_AGENTS):
                agent_id = SUPPORTED_AGENTS[index - 1][0]
                if agent_id in chosen:
                    chosen.remove(agent_id)
                else:
                    chosen.add(agent_id)


def _ensure_workflow_directories(root):
    for relative in ("docs/plans", "docs/reviews"):
        (Path(root) / relative).mkdir(parents=True, exist_ok=True)


def _cfg_and_root(args, for_init=False):
    cfg, cfg_errs = load_config()
    if cfg is None:
        cfg = default_config()
    try:
        root = find_project_root(for_init=for_init)
    except ValueError as e:
        root = None
        if not for_init:
            # init can use git top-level
            try:
                root = find_project_root(for_init=True)
            except ValueError:
                root = None
    return cfg, cfg_errs, root


def _discover(cfg, no_cache=False):
    library_root = resolve_library_root(cfg)
    overrides = cfg.get("skill_overrides", {}) if isinstance(cfg, dict) else {}
    allowed_roots = cfg.get("allowed_roots", []) if isinstance(cfg, dict) else []
    from agent_skills.cache import cache_path
    cache_file = cache_path(cfg.get("generated_root") if isinstance(cfg, dict) else None)
    records, warnings, errors = discover_skills(
        library_root=library_root,
        allowed_roots=allowed_roots,
        overrides=overrides,
        no_cache=no_cache,
        cache_file=cache_file,
    )
    return library_root, records, warnings, errors


def cmd_list(args, cfg):
    no_cache = bool(getattr(args, "no_cache", False))
    library_root, records, warnings, errors = _discover(cfg, no_cache=no_cache)

    if getattr(args, "tech", ""):
        tech = args.tech.lower()
        records = [r for r in records if tech in (r.get("dir_name") or "").lower()
                   or tech in (r.get("declared_name") or "").lower()]

    filt = (getattr(args, "filter", "") or "").strip().lower()
    if filt:
        records = [r for r in records if filt in (r.get("dir_name") or "").lower()
                   or filt in (r.get("declared_name") or "").lower()
                   or filt in (r.get("description") or "").lower()]

    if getattr(args, "selected", False):
        try:
            root = find_project_root()
            m, _ = load_manifest(root)
            sel = set(selected_ids(m)) if m else set()
            records = [r for r in records if r["dir_name"] in sel]
        except ValueError:
            records = []
            root = None

        if root is not None and m is not None:
            agents_block = m.get("agents") or {}
            enabled = [a for a, v in agents_block.items()
                       if isinstance(v, dict) and v.get("enabled", True)]
            res = resolve_resolutions(records, [r["dir_name"] for r in records], enabled)
            print("\nPer-agent resolution:")
            print(resolution_summary(res))

    json_out = getattr(args, "json_out", False) or getattr(args, "json", False)
    if json_out:
        print(json.dumps({
            "library_root": str(library_root),
            "count": len(records),
            "skills": [{"dir_name": r["dir_name"], "declared_name": r["declared_name"],
                        "description": r["description"], "frontmatter_status": r["frontmatter_status"]}
                       for r in records],
            "warnings": warnings,
            "errors": errors,
        }, indent=2))
    else:
        print("Library: %s" % library_root)
        print("Skills: %d" % len(records))
        for r in records:
            desc = r["description"] or ""
            if len(desc) > 80:
                desc = desc[:77] + "..."
            print("- %s  [%s]  %s" % (r["dir_name"], r["frontmatter_status"], desc))
        if warnings:
            print("\nWarnings: %d" % len(warnings))
        if errors:
            print("Errors: %d" % len(errors), file=sys.stderr)
    return 0 if not errors else 1


def _curses_available():
    try:
        import curses
        return True
    except Exception:
        return False


def _curses_select(recs, initial_chosen=None, recommended_ids=None):
    import curses
    chosen = set(initial_chosen or set())
    recommended_ids = set(recommended_ids or ())
    cancelled = [False]
    idx = [0]
    page = [0]
    search = [""]
    PAGE_SIZE = 20
    # Memoization for filtered list and percent map, invalidated when search changes.
    _last_search = [None]
    _cached_filtered = [None]
    _cached_percents = [None]

    def filtered_recs():
        s = search[0].lower()
        if _cached_filtered[0] is not None and _last_search[0] == s:
            return _cached_filtered[0]
        if s:
            _cached_filtered[0] = [r for r in recs if s in (r["record"].get("dir_name") or "").lower()
                                   or s in (r["record"].get("declared_name") or "").lower()
                                   or s in (r["record"].get("description") or "").lower()]
        else:
            _cached_filtered[0] = [
                r for r in recs
                if r["record"].get("dir_name") in recommended_ids
                or r["record"].get("dir_name") in chosen
            ]
        _last_search[0] = s
        return _cached_filtered[0]

    def score_percent(filtered):
        if not filtered:
            return {}
        max_score = max(r["score"] for r in filtered)
        if max_score <= 0:
            return {r["record"]["dir_name"]: 0 for r in filtered}
        return {
            r["record"]["dir_name"]: min(10, round(r["score"] / max_score * 10))
            for r in filtered
        }

    def percents_for(filtered):
        """Memoized score percent map, invalidated when search changes."""
        if _cached_percents[0] is not None and _last_search[0] == search[0].lower():
            return _cached_percents[0]
        _cached_percents[0] = score_percent(filtered)
        return _cached_percents[0]

    def page_count(filtered):
        return max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _init_colors(stdscr):
        try:
            curses.start_color()
            curses.use_default_colors()
            # Pair 1: selected row (hover) — black text on cyan background
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
            # Pair 2: header / title
            curses.init_pair(2, curses.COLOR_CYAN, -1)
            # Pair 3: check mark / selected skill
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            # Pair 4: search bar (typed text)
            curses.init_pair(4, curses.COLOR_WHITE, -1)
            # Pair 5: footer / hints
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)
            # Pair 6: score percent (matching percentage) — yellow
            curses.init_pair(6, curses.COLOR_YELLOW, -1)
            # Pair 7: secondary text (stats, borders, empty state) — cyan dim
            curses.init_pair(7, curses.COLOR_CYAN, -1)
        except curses.error:
            pass

    def draw(stdscr):
        _init_colors(stdscr)
        curses.curs_set(0)
        stdscr.keypad(True)
        while True:
            filtered = filtered_recs()
            page[0] = max(0, min(page[0], page_count(filtered) - 1))
            if idx[0] >= len(filtered):
                idx[0] = max(0, len(filtered) - 1)
            # Page-local window.
            start = page[0] * PAGE_SIZE
            end = start + PAGE_SIZE
            page_items = filtered[start:end]
            if idx[0] < start or idx[0] >= end:
                idx[0] = start if page_items else 0
            local_idx = idx[0] - start if page_items else 0
            percents = percents_for(filtered)

            stdscr.clear()
            h, w = stdscr.getmaxyx()

            # Title bar.
            try:
                title = " Agent Skill Selector "
                pad = max(0, (w - len(title)) // 2)
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                stdscr.addstr(0, pad, title[: max(1, w - 1)])
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            except curses.error:
                pass

            # Search line — typed text highlighted.
            try:
                stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
                stdscr.addstr(1, 1, "Search: ")
                stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)
                stdscr.attron(curses.color_pair(4) | curses.A_BOLD | curses.A_STANDOUT)
                stdscr.addstr(search[0])
                stdscr.attroff(curses.color_pair(4) | curses.A_BOLD | curses.A_STANDOUT)
                stdscr.addstr("  (recommendations shown; type to search all)")
            except curses.error:
                pass

            # Stats line: page + selected count.
            try:
                stats = "Page %d/%d  (%d skills, %d selected)" % (
                    page[0] + 1, page_count(filtered), len(filtered), len(chosen))
                stdscr.attron(curses.color_pair(7) | curses.A_DIM)
                stdscr.addstr(1, max(0, w - len(stats) - 1), stats)
                stdscr.attroff(curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass

            # Content area border.
            content_top = 3
            try:
                stdscr.attron(curses.color_pair(7) | curses.A_DIM)
                stdscr.addstr(content_top - 1, 0, "─" * max(1, w - 1))
                stdscr.attroff(curses.color_pair(7) | curses.A_DIM)
                # Column hints.
                hint = "  [mark]  serial. name                   score"
                stdscr.addstr(content_top - 1, 1, hint[: max(1, w - 2)])
            except curses.error:
                pass

            if not page_items:
                try:
                    stdscr.attron(curses.color_pair(7) | curses.A_DIM)
                    stdscr.addstr(content_top, 1, "No skills match your search.")
                    stdscr.attroff(curses.color_pair(7) | curses.A_DIM)
                except curses.error:
                    pass
            else:
                for i, r in enumerate(page_items):
                    name = r["record"]["dir_name"]
                    mark = "x" if name in chosen else " "
                    pct = percents.get(name, 0)
                    serial = start + i + 1
                    left = "  [%s] %2d. %s" % (mark, serial, name)
                    score_str = "%d/10" % pct
                    score_x = w - len(score_str) - 1
                    max_left = max(0, score_x - 1)
                    left_disp = left[:max_left]
                    try:
                        if i == local_idx:
                            stdscr.attron(curses.color_pair(1))
                        elif name in chosen:
                            stdscr.attron(curses.color_pair(3))
                        stdscr.addstr(content_top + i, 0, left_disp[: max(1, w - 1)])
                        # Drop chosen color before scoring so score isn't tinted green.
                        if i != local_idx and name in chosen:
                            stdscr.attroff(curses.color_pair(3))
                        if score_x > len(left_disp):
                            gap = " " * max(0, score_x - len(left_disp))
                            if i == local_idx:
                                stdscr.attron(curses.color_pair(1))
                                stdscr.addstr(content_top + i, len(left_disp), gap[: max(1, w - len(left_disp))])
                                stdscr.addstr(content_top + i, score_x, score_str[: max(1, w - score_x)])
                                stdscr.attroff(curses.color_pair(1))
                            else:
                                stdscr.addstr(content_top + i, len(left_disp), gap[: max(1, w - len(left_disp))])
                                if pct >= 10:
                                    stdscr.attron(curses.color_pair(3))
                                elif pct >= 7:
                                    stdscr.attron(curses.color_pair(6))
                                stdscr.addstr(content_top + i, score_x, score_str[: max(1, w - score_x)])
                                if pct >= 10:
                                    stdscr.attroff(curses.color_pair(3))
                                elif pct >= 7:
                                    stdscr.attroff(curses.color_pair(6))
                        if i == local_idx:
                            stdscr.attroff(curses.color_pair(1))
                        elif name in chosen:
                            stdscr.attroff(curses.color_pair(3))
                    except curses.error:
                        pass

            # Scroll indicator.
            try:
                if page_count(filtered) > 1:
                    scroll = "▼" if page[0] < page_count(filtered) - 1 else ""
                    stdscr.attron(curses.color_pair(2))
                    stdscr.addstr(h - 2, max(0, w - 4), scroll)
                    stdscr.attroff(curses.color_pair(2))
            except curses.error:
                pass

            # Footer / key hints.
            try:
                footer = " ↑↓ move  PgUp/PgDn page  Space toggle  Enter confirm  q cancel"
                stdscr.attron(curses.color_pair(5) | curses.A_DIM)
                stdscr.addstr(h - 1, 1, footer[: max(1, w - 2)])
                stdscr.attroff(curses.color_pair(5) | curses.A_DIM)
            except curses.error:
                pass

            stdscr.refresh()
            key = stdscr.getch()
            if key == curses.KEY_UP:
                idx[0] = max(0, idx[0] - 1)
            elif key == curses.KEY_DOWN:
                idx[0] = min(len(filtered) - 1, idx[0] + 1)
            elif key == curses.KEY_NPAGE:  # PgDn
                page[0] = min(page[0] + 1, page_count(filtered) - 1)
                idx[0] = page[0] * PAGE_SIZE
            elif key == curses.KEY_PPAGE:  # PgUp
                page[0] = max(page[0] - 1, 0)
                idx[0] = page[0] * PAGE_SIZE
            elif key == ord(" "):
                if filtered:
                    name = filtered[idx[0]]["record"]["dir_name"]
                    if name in chosen:
                        chosen.discard(name)
                    else:
                        chosen.add(name)
            elif key in (10, 13, curses.KEY_ENTER):
                return
            elif key in (ord("q"), ord("Q"), 27):
                cancelled[0] = True
                return None
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                if search[0]:
                    search[0] = search[0][:-1]
                    page[0] = 0
                    idx[0] = 0
            elif 32 <= key < 127:
                search[0] += chr(key)
                page[0] = 0
                idx[0] = 0

    curses.wrapper(draw)
    if cancelled[0]:
        return None
    return sorted(chosen)


def interactive_select(records, techs, limit=20, show_all=False, initial_selected=None, filt="", tech=""):
    # Apply user filter (substring match on dir_name, declared_name, description).
    if filt:
        f = filt.lower()
        filtered = []
        for r in records:
            haystack = " ".join([
                r.get("dir_name") or "",
                r.get("declared_name") or "",
                r.get("description") or "",
            ]).lower()
            if f in haystack:
                filtered.append(r)
        records = filtered
    # If a single tech is requested, restrict candidates to those with a tech
    # keyword overlap in their dir_name / declared_name / description.
    if tech:
        t = tech.lower()
        filtered = []
        for r in records:
            haystack = " ".join([
                r.get("dir_name") or "",
                r.get("declared_name") or "",
                r.get("description") or "",
            ]).lower()
            if t in haystack:
                filtered.append(r)
        records = filtered
    if not records:
        print("No matching skills.")
        return []
    if _curses_available() and sys.stdin.isatty() and sys.stdout.isatty():
        try:
            from agent_skills.recommend import score_skill
            selected_set = set(initial_selected or set())
            recommended = recommend(
                records, techs, limit=limit, all_results=show_all,
            )
            all_recs = []
            for r in records:
                s, reasons = score_skill(r, techs)
                all_recs.append({"record": r, "score": s,
                                 "reasons": reasons if reasons else ["no strong signal"]})
            # Previously selected skills first, then descending match score,
            # then dir_name ascending (deterministic).
            all_recs.sort(key=lambda x: (
                x["record"]["dir_name"] not in selected_set,
                -x["score"],
                x["record"].get("dir_name", ""),
            ))
            return _curses_select(
                all_recs,
                initial_chosen=selected_set,
                recommended_ids={
                    item["record"]["dir_name"] for item in recommended
                },
            )
        except Exception:
            pass

    chosen = set(initial_selected or set())
    while True:
        query = filt.strip().lower()
        candidates = [
            record for record in records
            if not query or query in " ".join((
                record.get("dir_name") or "",
                record.get("declared_name") or "",
                record.get("description") or "",
            )).lower()
        ]
        if query or show_all:
            recs = recommend(
                candidates, techs, limit=len(candidates), all_results=True,
            )
            view_name = "Search results" if query else "All skills"
        else:
            recs = recommend(candidates, techs, limit=limit)
            view_name = "Recommendations"
        rec_names = {item["record"]["dir_name"] for item in recs}
        if not query:
            for record in records:
                if record["dir_name"] in chosen and record["dir_name"] not in rec_names:
                    recs.append({
                        "record": record, "score": 0,
                        "reasons": ["currently selected"],
                    })
        if not recs:
            print("No recommendations. Search with 's <text>' or browse all with 'a'.")
            try:
                raw = input("> ").strip()
            except EOFError:
                return None
            if raw.lower() in ("", "done", "ok"):
                return sorted(chosen)
            if raw.lower() == "q":
                return None
            if raw.lower() in ("r", "c"):
                show_all = False
                filt = ""
            elif raw.lower() == "a":
                show_all = True
                filt = ""
            elif raw.lower().startswith("s "):
                filt = raw[2:].strip()
                show_all = True
            elif raw.startswith("/"):
                filt = raw[1:].strip()
                show_all = True
            continue
        print("\n%s (toggle numbers; s <text> searches all skills; 'a' browses all; "
              "'r' returns to recommendations; Enter confirms; 'q' cancels):" % view_name)
        for i, r in enumerate(recs, start=1):
            mark = "x" if r["record"]["dir_name"] in chosen else " "
            print("  [%s] %2d. %s (score=%d)" % (mark, i, r["record"]["dir_name"], r["score"]))
        try:
            raw = input("> ").strip()
        except EOFError:
            return None
        if raw.lower() in ("", "done", "ok"):
            return sorted(chosen)
        if raw.lower() == "q":
            return None
        if raw.lower() == "a":
            show_all = True
            filt = ""
            continue
        if raw.lower() == "r":
            show_all = False
            filt = ""
            continue
        if raw.lower() == "c":
            show_all = False
            filt = ""
            continue
        if raw.lower().startswith("s "):
            filt = raw[2:].strip()
            show_all = True
            continue
        if raw.startswith("/"):
            filt = raw[1:].strip()
            show_all = True
            continue
        for tok in raw.split():
            try:
                idx = int(tok)
            except ValueError:
                continue
            if 1 <= idx <= len(recs):
                name = recs[idx - 1]["record"]["dir_name"]
                if name in chosen:
                    chosen.discard(name)
                else:
                    chosen.add(name)
    return sorted(chosen)


def cmd_select(args, cfg):
    try:
        root = find_project_root(for_init=True)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    techs = detect_technologies(root)
    library_root, records, warnings, errors = _discover(
        cfg,
        no_cache=getattr(args, "dry_run", False) or getattr(args, "no_cache", False),
    )
    if errors:
        for e in errors:
            print("error: %s" % e, file=sys.stderr)
        return 1
    man, manifest_errors = load_manifest(root)
    if man is not None and manifest_errors:
        print("error: invalid manifest: %s" % "; ".join(manifest_errors), file=sys.stderr)
        return 1
    if man is None and manifest_path(root).exists():
        print("error: unable to load existing manifest: %s" % "; ".join(manifest_errors), file=sys.stderr)
        return 1
    initial = set(selected_ids(man)) if man else set()
    if not sys.stdin.isatty():
        print("error: interactive selection requires a TTY; --yes only confirms writes", file=sys.stderr)
        return 4
    chosen = interactive_select(
        records, techs, limit=getattr(args, "limit", 20),
        show_all=getattr(args, "all", False), initial_selected=initial,
        filt=getattr(args, "filter", ""), tech=getattr(args, "tech", ""),
    )
    if chosen is None:
        print("Selection cancelled.")
        return 0
    for sid in chosen:
        if not identity.is_safe_id(sid):
            print("error: unsafe skill id %r (cannot be selected)" % sid, file=sys.stderr)
            return 1
    if getattr(args, "dry_run", False):
        print("would select: %s" % ", ".join(chosen))
        return 0
    if man is None:
        man = default_manifest(root.name)
    # Replace selection entirely so unchecked skills are removed.
    man.setdefault("skills", {})["selected"] = list(chosen)
    if not _confirm("Select %s?" % ", ".join(chosen), getattr(args, "yes", False)):
        return 0
    save_manifest(root, man)
    print("Updated %s" % manifest_path(root))
    return 0


def cmd_init(args, cfg):
    try:
        root = find_project_root(for_init=True)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    mp = manifest_path(root)
    dry_run = getattr(args, "dry_run", False)
    interactive = getattr(args, "interactive", False)
    yes = getattr(args, "yes", False)
    if interactive and not sys.stdin.isatty():
        print("error: guided initialization requires a TTY; --yes only confirms writes", file=sys.stderr)
        return 4

    if mp.exists():
        man, errs = load_manifest(root)
        if man is None or errs:
            print("error: invalid existing manifest: %s" % (
                "; ".join(errs) if errs else "invalid manifest",
            ), file=sys.stderr)
            return 1
    else:
        man = default_manifest(args.name or root.name)
    if args.name:
        man.setdefault("project", {})["name"] = args.name

    techs = detect_technologies(root)
    try:
        library_root, records, warnings, errors = _discover(cfg, no_cache=dry_run)
    except DiscoveryError as error:
        library_root = resolve_library_root(cfg)
        if library_root.exists():
            print("error: unable to discover skills: %s" % error, file=sys.stderr)
            return 1
        records, errors = [], []
        warnings = ["skill library is not initialized: %s" % library_root]
    if errors:
        for error in errors:
            print("error: %s" % error, file=sys.stderr)
        return 1
    for warning in warnings:
        print("notice: %s" % warning, file=sys.stderr)
    recs = recommend(records, techs, limit=20)

    print("Project root: %s" % root)
    print("Detected technologies:")
    for t in techs:
        print("  - %s (%s)" % (t["name"], ", ".join(e["file"] for e in t["evidence"])))
    print("\n%s:" % (
        "Recommended skills (choose below; none are auto-selected)"
        if interactive else "Recommended skills (not auto-selected)"
    ))
    for rec in recs:
        print("  - %s (score=%d): %s" % (
            rec["record"]["dir_name"], rec["score"], "; ".join(rec["reasons"]),
        ))

    existing_manifest = mp.exists()
    if interactive:
        agents = man.get("agents")
        agents = agents if isinstance(agents, dict) else {}
        initial_agents = [
            agent_id for agent_id, _ in SUPPORTED_AGENTS
            if agent_is_enabled({"agents": agents}, agent_id)
        ]
        chosen_agents = interactive_select_agents(cfg, initial_agents)
        if chosen_agents is None:
            print("Initialization cancelled.")
            return 0

        existing_skill_ids = selected_ids(man)
        chosen_skills = interactive_select(
            records, techs, limit=20,
            initial_selected=set(existing_skill_ids),
        )
        if chosen_skills is None:
            print("Initialization cancelled.")
            return 0
        available_ids = {record["dir_name"] for record in records}
        missing_selected = set(existing_skill_ids) - available_ids
        if missing_selected:
            print(
                "notice: retaining selected skills not currently in the library: %s"
                % ", ".join(sorted(missing_selected)),
                file=sys.stderr,
            )
            chosen_skills = sorted(set(chosen_skills) | missing_selected)
        for skill_id in chosen_skills:
            if not identity.is_safe_id(skill_id):
                print("error: unsafe skill id %r (cannot be selected)" % skill_id, file=sys.stderr)
                return 1

        updated_agents = dict(agents)
        enabled_agents = set(chosen_agents)
        for agent_id, _ in SUPPORTED_AGENTS:
            settings = updated_agents.get(agent_id)
            settings = dict(settings) if isinstance(settings, dict) else {}
            settings["enabled"] = agent_id in enabled_agents
            updated_agents[agent_id] = settings
        man["agents"] = updated_agents
        skills = man.get("skills")
        skills = dict(skills) if isinstance(skills, dict) else {}
        skills["selected"] = list(chosen_skills)
        man["skills"] = skills

    manifest_errors = validate_manifest(man)
    if manifest_errors:
        print("error: invalid project manifest: %s" % "; ".join(manifest_errors), file=sys.stderr)
        return 1
    _, agents_preview_message, agents_preview = generate_agents_md(
        root, techs, cfg, write=False,
    )
    if agents_preview is None:
        print("error: %s" % agents_preview_message, file=sys.stderr)
        return 1

    if dry_run:
        if existing_manifest and not interactive:
            print("would preserve existing manifest: %s" % mp)
        else:
            print("would %s manifest: %s" % (
                "update" if existing_manifest else "create", mp,
            ))
        if interactive:
            print("selected agents: %s" % (
                ", ".join(chosen_agents) if chosen_agents else "(none)",
            ))
            print("selected skills: %s" % (
                ", ".join(chosen_skills) if chosen_skills else "(none)",
            ))
        print("would update managed AGENTS.md block")
        print("would create docs/plans/ and docs/reviews/")
        return 0

    if not existing_manifest or interactive:
        prompt = (
            "Update project setup with agents [%s] and skills [%s]?"
            % (", ".join(chosen_agents), ", ".join(chosen_skills))
            if interactive else "Create manifest with empty selection?"
        )
        if not _confirm(prompt, yes):
            if not sys.stdin.isatty() and not yes:
                print("error: confirmation required (non-TTY); use --yes", file=sys.stderr)
                return 4
            print("Initialization cancelled.")
            return 0
        save_manifest(root, man)
        print("%s %s" % ("Updated" if existing_manifest else "Created", mp))
    else:
        print("manifest already exists: %s" % mp)

    _, msg, content = generate_agents_md(root, techs, cfg)
    print(msg)
    if content is None:
        return 1
    try:
        _ensure_workflow_directories(root)
    except OSError as error:
        print("error: failed to create docs/plans/ and docs/reviews/: %s" % error, file=sys.stderr)
        return 1
    print("Ensured docs/plans/ and docs/reviews/")
    return 0


def cmd_add(args, cfg):
    try:
        root = find_project_root()
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    man, errs = load_manifest(root)
    if man is None:
        print("error: %s" % "; ".join(errs), file=sys.stderr)
        return 1
    library_root, records, warnings, errors = _discover(
        cfg, no_cache=getattr(args, "dry_run", False),
    )
    known = {r["dir_name"]: r for r in records}
    sel = selected_ids(man)
    for sid in args.skills:
        if not identity.is_safe_id(sid):
            print("error: unsafe skill id %r (cannot be selected)" % sid, file=sys.stderr)
            return 1
        if sid not in known:
            print("error: unknown skill %r" % sid, file=sys.stderr)
            return 1
        if sid in sel:
            print("error: already selected %r" % sid, file=sys.stderr)
            return 1
        sel.append(sid)
    if getattr(args, "dry_run", False):
        print("would add: %s" % ", ".join(args.skills))
        return 0
    man.setdefault("skills", {})["selected"] = sel
    if not _confirm("Add %s to manifest?" % ", ".join(args.skills), getattr(args, "yes", False)):
        if not sys.stdin.isatty() and not getattr(args, "yes", False):
            print("error: confirmation required (non-TTY); use --yes", file=sys.stderr)
            return 4
        return 0
    save_manifest(root, man)
    print("Updated %s" % manifest_path(root))
    return 0


def cmd_remove(args, cfg):
    try:
        root = find_project_root()
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    man, errs = load_manifest(root)
    if man is None:
        print("error: %s" % "; ".join(errs), file=sys.stderr)
        return 1
    sel = selected_ids(man)
    for sid in args.skills:
        if sid not in sel:
            print("error: not selected %r" % sid, file=sys.stderr)
            return 1
    new_sel = [s for s in sel if s not in args.skills]
    if getattr(args, "dry_run", False):
        print("would remove: %s" % ", ".join(args.skills))
        return 0
    man.setdefault("skills", {})["selected"] = new_sel
    if not _confirm("Remove %s from manifest?" % ", ".join(args.skills), getattr(args, "yes", False)):
        if not sys.stdin.isatty() and not getattr(args, "yes", False):
            print("error: confirmation required (non-TTY); use --yes", file=sys.stderr)
            return 4
        return 0
    save_manifest(root, man)
    print("Updated %s" % manifest_path(root))
    return 0


def cmd_detect(args, cfg):
    try:
        root = find_project_root(for_init=True)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    techs = detect_technologies(root)
    if getattr(args, "json", False):
        print(json.dumps(techs, indent=2))
    else:
        for t in techs:
            print("%s: %s" % (t["name"], ", ".join(e["file"] for e in t["evidence"])))
    return 0


def cmd_recommend(args, cfg):
    try:
        root = find_project_root(for_init=True)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    techs = detect_technologies(root)
    library_root, records, warnings, errors = _discover(cfg, no_cache=getattr(args, "no_cache", False))
    recs = recommend(records, techs, limit=getattr(args, "limit", 20), all_results=getattr(args, "all", False))
    if getattr(args, "json", False):
        print(json.dumps([{"dir_name": r["record"]["dir_name"], "score": r["score"], "reasons": r["reasons"]} for r in recs], indent=2))
    else:
        for r in recs:
            print("%s  score=%d  %s" % (r["record"]["dir_name"], r["score"], "; ".join(r["reasons"])))
    return 0


def cmd_validate(args, cfg):
    # config
    cfg2, cfg_errs = load_config()
    ok = True
    if cfg_errs:
        ok = False
        print("config errors: %s" % "; ".join(cfg_errs))
    # library
    try:
        library_root, records, warnings, errors = _discover(cfg, no_cache=True)
        if errors:
            ok = False
            for e in errors:
                print("discovery error: %s" % e)
        print("library: %s (%d skills)" % (library_root, len(records)))
    except Exception as e:
        ok = False
        print("discovery failed: %s" % e)
        records = []
        library_root = None
    # manifest
    try:
        root = find_project_root()
        man, merrs = load_manifest(root)
        if merrs:
            ok = False
            for e in merrs:
                print("manifest error: %s" % e)
        else:
            # validate selected exist
            sel = selected_ids(man)
            rec_map = {r["dir_name"]: r for r in records} if records else {}
            for sid in sel:
                if sid not in rec_map:
                    ok = False
                    print("manifest references missing skill: %s" % sid)
            print("manifest: %s (selected=%d)" % (manifest_path(root), len(sel)))

            # Per-agent resolution breakdown (§2.2).
            agents_block = (man.get("agents") or {}) if isinstance(man, dict) else {}
            enabled = [a for a, v in agents_block.items()
                       if isinstance(v, dict) and v.get("enabled", True)]
            res = resolve_resolutions(rec_map.values() if rec_map else [], sel, enabled)
            print("\nPer-agent resolution:")
            print(resolution_summary(res))

            # Validate only the manager-owned block; validation must not write.
            agents_md_path = root / "AGENTS.md"
            if not agents_md_path.is_file():
                ok = False
                print("AGENTS.md missing: run 'agent-skills init' or 'agent-skills sync' to generate.")
            else:
                techs = detect_technologies(root)
                try:
                    existing = agents_md_path.read_text(encoding="utf-8")
                    _, msg, expected_content = generate_agents_md(
                        root, techs, cfg, write=False,
                    )
                    if expected_content is None:
                        raise ValueError(msg)
                    expected = extract_agents_block(expected_content)
                    actual = extract_agents_block(existing)
                except OSError:
                    ok = False
                    expected = None
                    actual = None
                    print("AGENTS.md error: unable to read file")
                except ValueError as e:
                    ok = False
                    print("AGENTS.md error: %s" % e)
                    expected = None
                    actual = None
                if expected is not None and actual != expected:
                    ok = False
                    print("AGENTS.md stale: regenerate with 'agent-skills sync'.")
    except ValueError as e:
        ok = False
        print("no project root: %s" % e)
    return 0 if ok else 3


def cmd_sync(args, cfg):
    try:
        root = find_project_root()
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    man, errs = load_manifest(root)
    if man is None:
        print("error: %s" % "; ".join(errs), file=sys.stderr)
        return 1
    sel = selected_ids(man)
    library_root, records, warnings, errors = _discover(
        cfg, no_cache=getattr(args, "dry_run", False),
    )
    rec_map = {r["dir_name"]: r for r in records}
    selected_records = []
    for sid in sel:
        if sid in rec_map:
            selected_records.append(rec_map[sid])
        else:
            print("error: selected skill missing from library: %s" % sid, file=sys.stderr)
            return 1
    # Detect technologies for relevance-based budget filtering.
    techs = detect_technologies(root)
    dry_run = args.dry_run
    wrote_agents, msg_agents, agents_md_content = generate_agents_md(
        root, techs, cfg, write=not dry_run,
    )
    if msg_agents:
        print("notice: %s" % msg_agents)
    if agents_md_content is None:
        print("error: %s" % msg_agents, file=sys.stderr)
        return 1
    # Context budget filtering: only generate skills that fit in context.
    filtered_records, skipped, total_tokens, cwarnings = filter_skills_for_context(
        selected_records, sel, techs,
        cfg.get("skill_context_budget_tokens") if isinstance(cfg, dict) else 32768,
        cfg.get("max_skills_in_context") if isinstance(cfg, dict) else 50,
    )
    if cwarnings:
        for w in cwarnings:
            print("notice: %s" % w, file=sys.stderr)
    generated_root = cfg.get("generated_root") if isinstance(cfg, dict) else None
    from pathlib import Path
    if not generated_root:
        generated_root = str(Path.home() / ".local" / "share" / "agent-skills" / "projects")
    # project key
    import hashlib
    key = "%s-%s" % (root.name, hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12])
    gen_dir = Path(generated_root) / key
    if dry_run:
        print("would generate: %s with %d skills" % (gen_dir, len(filtered_records)))
        if agents_md_content:
            print("would write AGENTS.md into generated dir")
        return 0
    lock_path = Path(generated_root) / ".lock"
    try:
        with AdvisoryLock(lock_path):
            build_skills_dir_atomic(
                parent=gen_dir.parent,
                dest_dir=gen_dir,
                records=filtered_records,
                agent_name="manager",
                key=key,
                build_entry_fn=build_skill_entry,
                tmp_prefix=".gen-tmp-",
                agents_md_content=agents_md_content,
                owned_rules_filename=OWNED_RULES_FILENAME,
            )
    except LockError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    except (OSError, RuntimeError) as e:
        print("error: failed to generate project skills: %s" % e, file=sys.stderr)
        return 1
    print("generated: %s" % gen_dir)
    return 0


def cmd_doctor(args, cfg):
    import shutil
    from pathlib import Path
    print("Python: %s" % sys.version.split()[0])
    print("agent-skills: %s" % __version__)
    # PATH check
    path = os.environ.get("PATH", "")
    local_bin = str(Path.home() / ".local" / "bin")
    print("~/.local/bin on PATH: %s" % (local_bin in path.split(os.pathsep)))
    if local_bin not in path.split(os.pathsep):
        print("  add to ~/.zshrc: export PATH=\"$HOME/.local/bin:$PATH\"")
    launcher = Path(local_bin) / "agent-skills"
    print("agent-skills binary: %s" % ("found" if launcher.is_file() else "MISSING"))
    if not launcher.is_file():
        print("  run ./install.sh to install the launcher")
    # agent versions
    tested = cfg.get("tested_agent_versions", {}) if isinstance(cfg, dict) else {}
    for agent, ver in tested.items():
        print("tested %s: %s" % (agent, ver))
    # library
    try:
        library_root, records, warnings, errors = _discover(cfg, no_cache=True)
        print("library: %s (%d skills, %d warnings, %d errors)" % (library_root, len(records), len(warnings), len(errors)))
    except Exception as e:
        print("library check failed: %s" % e)
    # context budget
    bgt = cfg.get("skill_context_budget_tokens") if isinstance(cfg, dict) else 32768
    msc = cfg.get("max_skills_in_context") if isinstance(cfg, dict) else 50
    print("context budget: %d tokens, max %d skills" % (bgt, msc))
    if bgt and bgt <= 0:
        print("  warning: skill_context_budget_tokens is 0 (unlimited)")
    if msc and msc <= 0:
        print("  warning: max_skills_in_context is 0 (unlimited)")
    return 0


def _project_root_exists_for_prefix(prefix):
    """Return True if a directory named `prefix` containing .agents/skills.json exists."""
    if not prefix:
        return False
    # Search from cwd upward.
    cur = Path.cwd().resolve()
    while True:
        candidate = cur / prefix
        if candidate.is_dir() and (candidate / ".agents" / "skills.json").is_file():
            return True
        if cur.parent == cur:
            break
        cur = cur.parent
    # Also check home directory children.
    try:
        for entry in Path.home().iterdir():
            if entry.is_dir() and entry.name == prefix:
                if (entry / ".agents" / "skills.json").is_file():
                    return True
    except OSError:
        pass
    return False


def cmd_clean(args, cfg):
    generated_root = cfg.get("generated_root") if isinstance(cfg, dict) else None
    from pathlib import Path
    if not generated_root:
        generated_root = str(Path.home() / ".local" / "share" / "agent-skills" / "projects")
    gr = Path(generated_root)
    if not gr.exists():
        print("nothing to clean")
        return 0
    orphans = []
    for d in gr.iterdir():
        if not d.is_dir():
            continue
        marker = read_marker(d)
        if marker is None:
            continue
        pk = marker.get("project_key", "")
        prefix = pk.rsplit("-", 1)[0] if pk else ""
        if prefix and _project_root_exists_for_prefix(prefix):
            continue  # project root still exists; not an orphan
        orphans.append(d)
    dry = args.dry_run
    for d in orphans:
        if dry:
            print("would remove: %s" % d)
        else:
            if _confirm("Remove %s?" % d, getattr(args, "yes", False)):
                import shutil
                shutil.rmtree(d)
                print("removed: %s" % d)
    if not orphans:
        print("no managed directories found")
    return 0


def cmd_junie(args, cfg):
    # Phase 5: managed launch. Implement basic.
    from agent_skills.adapters.junie import launch_junie
    return launch_junie(args, cfg)


def cmd_kilo(args, cfg):
    from agent_skills.adapters.kilo import launch_kilo, kilo_plan, kilo_validate
    sub = getattr(args, "kilo_sub", None)
    if sub == "plan":
        rc, msg = kilo_plan(cfg)
        print(msg)
        return rc
    if sub == "apply":
        return launch_kilo(args, cfg)
    if sub == "validate":
        rc, msg = kilo_validate(cfg)
        print(msg)
        return rc
    if sub == "run":
        args.run_kilo = True
        return launch_kilo(args, cfg)
    print("unknown kilo subcommand", file=sys.stderr)
    return 2


def cmd_opencode(args, cfg):
    from agent_skills.adapters.opencode import run_opencode_subcommand
    return run_opencode_subcommand(args, cfg)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(argv)

    cfg, cfg_errs = load_config()
    if cfg is None:
        cfg = default_config()

    cmd = args.command
    if cmd is None:
        parser.print_help()
        return 0
    if cmd == "list":
        return cmd_list(args, cfg)
    if cmd == "init":
        return cmd_init(args, cfg)
    if cmd == "select":
        return cmd_select(args, cfg)
    if cmd == "add":
        return cmd_add(args, cfg)
    if cmd == "remove":
        return cmd_remove(args, cfg)
    if cmd == "detect":
        return cmd_detect(args, cfg)
    if cmd == "recommend":
        return cmd_recommend(args, cfg)
    if cmd == "validate":
        return cmd_validate(args, cfg)
    if cmd == "sync":
        return cmd_sync(args, cfg)
    if cmd == "doctor":
        return cmd_doctor(args, cfg)
    if cmd == "clean":
        return cmd_clean(args, cfg)
    if cmd == "junie":
        return cmd_junie(args, cfg)
    if cmd == "kilo":
        return cmd_kilo(args, cfg)
    if cmd == "opencode":
        return cmd_opencode(args, cfg)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())