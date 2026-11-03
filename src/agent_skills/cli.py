"""CLI for the agent skill manager."""

import argparse
import json
import os
import sys

from agent_skills import __version__
from agent_skills.config import load_config, resolve_library_root, default_config
from agent_skills.discovery import discover_skills, DiscoveryError
from agent_skills.manifest import (
    manifest_path, load_manifest, save_manifest, default_manifest, selected_ids, validate_manifest,
)
from agent_skills.project import find_project_root
from agent_skills.detection import detect_technologies
from agent_skills.recommend import recommend
from agent_skills.links import generate_project_skills_dir, read_marker
from agent_skills.lock import AdvisoryLock, LockError
from agent_skills import identity
from agent_skills.resolution import resolve_resolutions, resolution_summary


def _build_parser():
    parser = argparse.ArgumentParser(prog="agent-skills", description="Global agent skill manager")
    parser.add_argument("--version", action="version", version="agent-skills %s" % __version__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--no-cache", action="store_true", help="bypass discovery cache")
    parser.add_argument("--yes", action="store_true", help="accept confirmations")
    parser.add_argument("--dry-run", action="store_true", help="show changes, change nothing")

    sub = parser.add_subparsers(dest="command")

    # list
    p = sub.add_parser("list", help="list library skills")
    p.add_argument("--selected", action="store_true")
    p.add_argument("--filter", default="")
    p.add_argument("--tech", default="")
    p.add_argument("--json", action="store_true", dest="json_out")
    p.add_argument("--no-cache", action="store_true", dest="no_cache")

    # init
    p = sub.add_parser("init", help="create manifest with empty selection")
    p.add_argument("--name", default=None)
    p.add_argument("--interactive", action="store_true", help="run interactive selection after detection")
    p.add_argument("--yes", action="store_true", help="accept confirmations")

    # select
    p = sub.add_parser("select", help="interactively select skills from recommendations")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--all", action="store_true")
    p.add_argument("--filter", default="")
    p.add_argument("--tech", default="")

    # add
    p = sub.add_parser("add", help="add skills by dir_name")
    p.add_argument("skills", nargs="+")

    # remove
    p = sub.add_parser("remove", help="remove skills from manifest")
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
    sub.add_parser("sync", help="regenerate generated state from manifest")

    # doctor
    sub.add_parser("doctor", help="environment checks")

    # clean
    sub.add_parser("clean", help="remove orphaned generated directories")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")

    # junie
    p = sub.add_parser("junie", help="launch Junie with managed skills")
    p.add_argument("--prepare", action="store_true")
    p.add_argument("args", nargs=argparse.REMAINDER)

    # kilo
    p = sub.add_parser("kilo", help="Kilo subcommands")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--yes", action="store_true")
    sp = p.add_subparsers(dest="kilo_sub")
    for name in ("plan", "apply", "validate", "run"):
        subp = sp.add_parser(name, help="%s Kilo config" % name)
        subp.add_argument("args", nargs=argparse.REMAINDER)

    # opencode
    p = sub.add_parser("opencode", help="OpenCode subcommands")
    sp = p.add_subparsers(dest="oc_sub")
    for name in ("plan", "apply", "validate", "run"):
        subp = sp.add_parser(name, help="%s OpenCode config" % name)
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
    no_cache = args.no_cache or args.no_cache if hasattr(args, "no_cache") else args.no_cache
    # normalize
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


def _curses_select(recs, initial_chosen=None):
    import curses
    chosen = set(initial_chosen or set())
    idx = [0]
    page = [0]
    search = [""]
    PAGE_SIZE = 20

    def filtered_recs():
        s = search[0].lower()
        if not s:
            return recs
        return [r for r in recs if s in (r["record"].get("dir_name") or "").lower()
                or s in (r["record"].get("declared_name") or "").lower()
                or s in (r["record"].get("description") or "").lower()]

    def page_count(filtered):
        return max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _init_colors(stdscr):
        try:
            curses.start_color()
            curses.use_default_colors()
            # Pair 1: selected row (reverse video)
            curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
            # Pair 2: header / title
            curses.init_pair(2, curses.COLOR_CYAN, -1)
            # Pair 3: check mark / selected skill
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            # Pair 4: search bar (typed text)
            curses.init_pair(4, curses.COLOR_WHITE, -1)
            # Pair 5: footer / hints
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)
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
                stdscr.addstr(1, 1, "Search: %s" % search[0])
                stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)
                stdscr.addstr(1, 12 + len(search[0]), "  (type to filter, Backspace clear)")
            except curses.error:
                pass

            # Stats line: page + selected count.
            try:
                stats = "Page %d/%d  (%d skills, %d selected)" % (
                    page[0] + 1, page_count(filtered), len(filtered), len(chosen))
                stdscr.addstr(1, max(0, w - len(stats) - 1), stats)
            except curses.error:
                pass

            # Content area with border.
            content_top = 3
            try:
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(content_top - 1, 0, "─" * max(1, w - 1))
                stdscr.attroff(curses.A_DIM)
            except curses.error:
                pass

            if not page_items:
                try:
                    stdscr.addstr(content_top, 1, "No skills match your search.")
                except curses.error:
                    pass
            else:
                for i, r in enumerate(page_items):
                    name = r["record"]["dir_name"]
                    serial = start + i + 1
                    mark = "x" if name in chosen else " "
                    line = "  [%s] %2d. %s (score=%d)" % (mark, serial, name, r["score"])
                    try:
                        if i == local_idx:
                            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                            stdscr.addstr(content_top + i, 0, line[: max(1, w - 1)])
                            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                        else:
                            if name in chosen:
                                stdscr.attron(curses.color_pair(3))
                            stdscr.addstr(content_top + i, 0, line[: max(1, w - 1)])
                            if name in chosen:
                                stdscr.attroff(curses.color_pair(3))
                    except curses.error:
                        pass

            # Scroll indicator.
            try:
                if page_count(filtered) > 1:
                    scroll = "▼" if page[0] < page_count(filtered) - 1 else ""
                    stdscr.addstr(h - 2, max(0, w - 4), scroll)
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
                chosen.clear()
                return
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
    return sorted(chosen)


def interactive_select(records, techs, limit=20, show_all=False, initial_selected=None, filt="", tech=""):
    from agent_skills.recommend import recommend
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
    recs = recommend(records, techs, limit=limit, all_results=show_all)
    rec_names = {r["record"]["dir_name"] for r in recs}
    for r in records:
        if r["dir_name"] in (initial_selected or set()) and r["dir_name"] not in rec_names:
            recs.insert(0, {"record": r, "score": 0, "reasons": ["currently selected"]})
    if not recs:
        print("No recommendations.")
        return []

    if _curses_available() and sys.stdin.isatty() and sys.stdout.isatty():
        try:
            # Search bar operates on ALL discovered skills, not just
            # recommendations, so the user can find any skill by name.
            all_recs = [
                {"record": r, "score": 0, "reasons": ["all skills"]} for r in records
            ]
            return _curses_select(all_recs, initial_chosen=set(initial_selected or set()))
        except Exception:
            pass

    chosen = set(initial_selected or set())
    while True:
        print("\\nRecommendations (toggle numbers, Enter to confirm, 'q' to cancel):")
        for i, r in enumerate(recs, start=1):
            mark = "x" if r["record"]["dir_name"] in chosen else " "
            print("  [%s] %2d. %s (score=%d)" % (mark, i, r["record"]["dir_name"], r["score"]))
        try:
            raw = input("> ").strip()
        except EOFError:
            raw = ""
        if raw.lower() in ("", "done", "ok"):
            break
        if raw.lower() == "q":
            return []
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
    from agent_skills.recommend import recommend
    recs = recommend(records, techs, limit=limit, all_results=show_all)
    if not recs:
        print("No recommendations.")
        return []
    chosen = set()
    while True:
        print("\nRecommendations (toggle numbers, Enter to confirm, 'q' to cancel):")
        for i, r in enumerate(recs, start=1):
            mark = "x" if r["record"]["dir_name"] in chosen else " "
            print("  [%s] %2d. %s (score=%d)" % (mark, i, r["record"]["dir_name"], r["score"]))
        try:
            raw = input("> ").strip()
        except EOFError:
            raw = ""
        if raw.lower() in ("", "done", "ok"):
            break
        if raw.lower() == "q":
            return []
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
    library_root, records, warnings, errors = _discover(cfg, no_cache=getattr(args, "no_cache", False))
    if errors:
        for e in errors:
            print("error: %s" % e, file=sys.stderr)
        return 1
    man, _ = load_manifest(root)
    initial = set(selected_ids(man)) if man else set()
    if not sys.stdin.isatty() and not getattr(args, "yes", False):
        print("error: interactive selection requires a TTY or --yes", file=sys.stderr)
        return 4
    chosen = interactive_select(records, techs, limit=getattr(args, "limit", 20), show_all=getattr(args, "all", False), initial_selected=initial, filt=getattr(args, "filter", ""), tech=getattr(args, "tech", ""))
    if not chosen:
        print("No skills selected.")
        return 0
    man, errs = load_manifest(root)
    if man is None:
        man = default_manifest(root.name)
    # Replace selection entirely so unchecked skills are removed.
    man.setdefault("skills", {})["selected"] = list(chosen)
    if not _confirm("Select %s?" % ", ".join(chosen), getattr(args, "yes", False)):
        if not sys.stdin.isatty() and not getattr(args, "yes", False):
            print("error: confirmation required (non-TTY); use --yes", file=sys.stderr)
            return 4
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
    if mp.exists():
        print("manifest already exists: %s" % mp)
        # still show detection
    name = args.name or root.name
    man = default_manifest(name)
    # detect
    techs = detect_technologies(root)
    recs_list = []
    try:
        library_root, records, warnings, errors = _discover(cfg, no_cache=False)
        recs = recommend(records, techs, limit=20)
        recs_list = [{"dir_name": r["record"]["dir_name"], "score": r["score"], "reasons": r["reasons"]} for r in recs]
    except Exception as e:
        warnings = [str(e)]
    print("Project root: %s" % root)
    print("Detected technologies:")
    for t in techs:
        print("  - %s (%s)" % (t["name"], ", ".join(e["file"] for e in t["evidence"])))
    print("\nRecommended skills (not auto-selected):")
    for r in recs_list:
        print("  - %s (score=%d): %s" % (r["dir_name"], r["score"], "; ".join(r["reasons"])))
    if getattr(args, "interactive", False) and (sys.stdin.isatty() or getattr(args, "yes", False)):
        chosen = interactive_select(records, techs, limit=20)
        if chosen:
            sel = selected_ids(man) if man is not None else []
            for sid in chosen:
                if sid not in sel:
                    sel.append(sid)
            man.setdefault("skills", {})["selected"] = sel
            if _confirm("Create manifest with selection %s?" % ", ".join(chosen), getattr(args, "yes", False)):
                save_manifest(root, man)
                print("Created %s" % mp)
                return 0
    if not mp.exists():
        if not _confirm("Create manifest with empty selection?", getattr(args, "yes", False)):
            if not sys.stdin.isatty() and not getattr(args, "yes", False):
                print("error: confirmation required (non-TTY); use --yes", file=sys.stderr)
                return 4
            return 0
        save_manifest(root, man)
        print("Created %s" % mp)
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
    library_root, records, warnings, errors = _discover(cfg, no_cache=False)
    known = {r["dir_name"]: r for r in records}
    sel = selected_ids(man)
    for sid in args.skills:
        if sid not in known:
            print("error: unknown skill %r" % sid, file=sys.stderr)
            return 1
        if sid in sel:
            print("error: already selected %r" % sid, file=sys.stderr)
            return 1
        sel.append(sid)
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
                if sid not in rec_map and rec_map:
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
    except ValueError as e:
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
    library_root, records, warnings, errors = _discover(cfg, no_cache=False)
    rec_map = {r["dir_name"]: r for r in records}
    selected_records = []
    for sid in sel:
        if sid in rec_map:
            selected_records.append(rec_map[sid])
        else:
            print("error: selected skill missing from library: %s" % sid, file=sys.stderr)
            return 1
    generated_root = cfg.get("generated_root") if isinstance(cfg, dict) else None
    from pathlib import Path
    if not generated_root:
        generated_root = str(Path.home() / ".local" / "share" / "agent-skills" / "projects")
    # project key
    import hashlib
    key = "%s-%s" % (root.name, hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12])
    gen_dir = Path(generated_root) / key
    if getattr(args, "dry_run", False) or getattr(args, "dry-run", False):
        print("would generate: %s with %d skills" % (gen_dir, len(selected_records)))
        return 0
    lock_path = Path(generated_root) / ".lock"
    try:
        with AdvisoryLock(lock_path):
            generate_project_skills_dir(
                gen_dir, selected_records, library_root,
                allowed_roots=cfg.get("allowed_roots", []) if isinstance(cfg, dict) else [],
                project_key=key,
            )
    except LockError as e:
        print("error: %s" % e, file=sys.stderr)
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
        # We don't store root in manifest; heuristic: if name prefix root no longer exists? 
        # Clean only if marker exists but directory is stale? For Phase 3, list managed dirs.
        orphans.append(d)
    dry = getattr(args, "dry_run", False) or getattr(args, "dry-run", False)
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