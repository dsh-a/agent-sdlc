"""The ProjectReference closure of a sparse set, for `cycle/sparse-set.py`.

A project in the set builds only when every project it references is on disk, so the set grows to
the transitive closure of `<ProjectReference Include="...">` across the set's project files. Read
as XML with the standard library; `dotnet` is not needed. `Include` is relative to the referencing
project's directory and may use `\\` separators.

An `Include` holding an MSBuild property (`$(...)`) or a wildcard cannot be resolved without
MSBuild; it is named in a note and left out. A project file that does not parse makes the slot a
full checkout, since its references are unknown.
"""

from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET

PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj")


def _in(path: str, dirs: set[str]) -> bool:
    return any(path.startswith(d + "/") for d in dirs)


def closure(dirs: set[str], tracked: list[str], read) -> tuple[set[str], list[str], str | None]:
    """(directories to add, notes, full-checkout reason or None)."""
    projects = {p for p in tracked if p.endswith(PROJECT_SUFFIXES)}
    todo = [p for p in sorted(projects) if _in(p, dirs)]
    seen = set(todo)
    added: set[str] = set()
    notes: list[str] = []
    while todo:
        proj = todo.pop()
        try:
            root = ET.fromstring(read(proj))
        except ET.ParseError as e:
            return set(), [], f"{proj} does not parse as XML ({e}); its references are unknown"
        base = posixpath.dirname(proj)
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1] != "ProjectReference":
                continue
            for inc in (x.strip() for x in (el.get("Include") or "").split(";")):
                if not inc:
                    continue
                if "$(" in inc or "*" in inc or "?" in inc:
                    notes.append(f"{proj} references {inc}, which needs MSBuild to resolve; "
                                 f"not added")
                    continue
                target = posixpath.normpath(posixpath.join(base, inc.replace("\\", "/")))
                if target.startswith("../") or target not in projects:
                    notes.append(f"{proj} references {inc}, which is not a tracked project; "
                                 f"not added")
                    continue
                d = posixpath.dirname(target)
                if d and d not in dirs and not _in(target, dirs | added):
                    added.add(d)
                if target not in seen:
                    seen.add(target)
                    todo.append(target)
    for d in sorted(added):
        notes.append(f"ProjectReference closure adds {d}")
    return added, notes, None
