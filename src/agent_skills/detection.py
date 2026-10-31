"""Technology detection from project marker files."""

import os
from pathlib import Path

SKIP_DIRS = {"node_modules", "build", ".dart_tool", ".gradle", "Pods", "vendor", ".git", ".fvm"}


def _has_file(root, name):
    return (root / name).is_file()


def _read_text_safe(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(65536)
    except OSError:
        return ""


def _find_markers(root, max_depth=2):
    """Yield (relative_dir, filename) for marker files up to max_depth."""
    root = Path(root).resolve()
    results = []
    # depth 0
    for fn in os.listdir(root) if root.exists() else []:
        pass
    # We'll do recursive bounded walk.
    def walk(cur, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(cur))
        except OSError:
            return
        for name in entries:
            full = cur / name
            if full.is_dir():
                if name in SKIP_DIRS:
                    continue
                walk(full, depth + 1)
            else:
                results.append((cur, name))
    walk(root, 0)
    return results


def detect_technologies(project_root, max_depth=2):
    """Return list of dicts: {name, evidence: [{file, reason}]}."""
    root = Path(project_root).resolve()
    results = {}  # tech -> list of evidence dicts

    def add(tech, file, reason):
        results.setdefault(tech, []).append({"file": file, "reason": reason})

    # Collect marker files.
    markers = _find_markers(root, max_depth=max_depth)

    # Flutter/Dart
    for cur, fn in markers:
        if fn == "pubspec.yaml":
            rel = str((cur / fn).relative_to(root))
            text = _read_text_safe(cur / fn)
            if "flutter:" in text or "sdk: flutter" in text or "flutter" in text.lower():
                # Check dependency on flutter sdk.
                if "flutter" in text.lower():
                    add("flutter", rel, "pubspec.yaml references flutter")
                else:
                    add("dart", rel, "pubspec.yaml present")
            else:
                add("dart", rel, "pubspec.yaml present")

    # Determine if root is a Flutter project (for android/ exclusion).
    flutter_root = (root / "pubspec.yaml").is_file() and "flutter" in _read_text_safe(root / "pubspec.yaml").lower()

    # Java/Maven
    for cur, fn in markers:
        if fn == "pom.xml":
            rel = str((cur / fn).relative_to(root))
            # Skip if inside Flutter android/ and root is flutter.
            if flutter_root and _is_under_android(cur, root):
                continue
            text = _read_text_safe(cur / fn)
            if "spring-boot" in text:
                add("java-spring-boot", rel, "pom.xml references spring-boot")
            else:
                add("java-maven", rel, "pom.xml present")

    # Java/Gradle
    for cur, fn in markers:
        if fn in ("build.gradle", "build.gradle.kts"):
            rel = str((cur / fn).relative_to(root))
            if flutter_root and _is_under_android(cur, root):
                continue
            text = _read_text_safe(cur / fn)
            if "spring-boot" in text or "org.springframework.boot" in text:
                add("java-spring-boot", rel, "%s references spring-boot" % fn)
            else:
                add("java-gradle", rel, "%s present" % fn)

    # .NET
    for cur, fn in markers:
        if fn.endswith(".csproj") or fn.endswith(".sln") or fn.endswith(".slnx"):
            rel = str((cur / fn).relative_to(root))
            add("dotnet", rel, "%s present" % fn)

    # Laravel/PHP
    for cur, fn in markers:
        if fn == "composer.json":
            rel = str((cur / fn).relative_to(root))
            text = _read_text_safe(cur / fn)
            if "laravel/framework" in text:
                add("laravel", rel, "composer.json requires laravel/framework")
            else:
                add("php", rel, "composer.json present")
        if fn == "artisan":
            rel = str((cur / fn).relative_to(root))
            add("laravel", rel, "artisan present")

    # React / node
    for cur, fn in markers:
        if fn == "package.json":
            rel = str((cur / fn).relative_to(root))
            text = _read_text_safe(cur / fn)
            if '"react"' in text:
                add("react", rel, "package.json depends on react")
            else:
                add("node", rel, "package.json present")

    # Android native: settings.gradle(.kts) not nested in flutter project.
    if not flutter_root:
        for cur, fn in markers:
            if fn in ("settings.gradle", "settings.gradle.kts"):
                rel = str((cur / fn).relative_to(root))
                add("android", rel, "%s present" % fn)

    # Build result list.
    out = []
    for tech, evs in results.items():
        out.append({"name": tech, "evidence": evs})
    out.sort(key=lambda x: x["name"])
    return out


def _is_under_android(cur, root):
    try:
        rel = Path(cur).resolve().relative_to(root)
    except ValueError:
        return False
    parts = rel.parts
    return "android" in parts