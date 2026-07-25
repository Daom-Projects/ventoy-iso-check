from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ventoy_iso_check.catalog import load_catalog
from ventoy_iso_check.inventory import scan_isos
from ventoy_iso_check.models import Status


@dataclass
class SuggestEntry:
    filename: str
    relpath: str
    suggested_id: str
    label: str
    pattern: str
    version_guess: str | None
    yaml_snippet: str


def _slug_id(name: str) -> str:
    base = Path(name).stem.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-")
    # shorten noisy tails
    parts = base.split("-")
    if len(parts) > 4:
        parts = parts[:4]
    return "-".join(parts) or "unknown-iso"


def _guess_version(filename: str) -> str | None:
    stem = Path(filename).stem
    patterns = [
        r"(\d{4}\.\d+(?:\.\d+)*)",  # 2026.06, 2025.4
        r"(\d+\.\d+\.\d+-\d+)",  # clonezilla style
        r"(\d+\.\d+\.\d+)",
        r"(\d+\.\d+)",
        r"(\d{6})",  # cachyos YYMMDD
        r"(v?\d+\.\d+)",
    ]
    for p in patterns:
        m = re.search(p, stem, flags=re.I)
        if m:
            return m.group(1).lstrip("vV")
    return None


def _build_pattern(filename: str, version: str | None) -> str:
    """Build a case-insensitive regex that captures a version group when possible."""
    escaped = re.escape(filename)
    if version:
        # replace first occurrence of escaped version with a capture group
        ver_esc = re.escape(version)
        if ver_esc in escaped:
            # choose a reasonable capture shape
            if re.fullmatch(r"\d{6}", version):
                group = r"(\d{6})"
            elif re.fullmatch(r"\d+\.\d+\.\d+-\d+", version):
                group = r"(\d+\.\d+\.\d+-\d+)"
            elif re.fullmatch(r"\d+\.\d+\.\d+", version):
                group = r"(\d+\.\d+\.\d+)"
            elif re.fullmatch(r"\d{4}\.\d+(?:\.\d+)*", version):
                group = r"(\d{4}\.\d+(?:\.\d+)*)"
            elif re.fullmatch(r"\d+\.\d+", version):
                group = r"(\d+\.\d+)"
            else:
                group = r"([0-9][0-9A-Za-z._-]*)"
            body = escaped.replace(ver_esc, group, 1)
            return f"(?i)^{body}$"
    return f"(?i)^{escaped}$"


def _yaml_snippet(
    *,
    sid: str,
    label: str,
    pattern: str,
    page: str | None = None,
) -> str:
    lines = [
        f"  - id: {sid}",
        f"    label: {label}",
        "    patterns:",
        f"      - '{pattern}'",
        "    managed_by: catalog  # o manual | sisou",
        f"    page: {page or 'https://example.com/'}",
        "    resolver: none  # o nombre en resolvers.RESOLVERS",
        '    note: "Generado por ventoy-iso-check suggest — revisar y ajustar"',
        "",
    ]
    return "\n".join(lines)


def suggest_unsupported(
    root: Path,
    *,
    catalog_path: Path | None = None,
    deep: bool = False,
) -> list[SuggestEntry]:
    entries, defaults = load_catalog(catalog_path)
    skip = set(defaults.get("skip_dir_names") or [])
    exts = set(defaults.get("extensions") or [".iso", ".img"])
    items = scan_isos(
        root,
        entries,
        extensions=exts,
        skip_dirs=skip or None,
        deep=deep,
    )
    existing_ids = {e.id for e in entries}
    out: list[SuggestEntry] = []
    seen_ids: set[str] = set()

    for it in items:
        if it.status != Status.UNSUPPORTED and it.managed_by != "unsupported":
            # also suggest if catalog_id is None
            if it.catalog_id:
                continue
        if it.catalog_id:
            continue

        ver = _guess_version(it.filename)
        sid = _slug_id(it.filename)
        # uniquify
        base_sid = sid
        n = 2
        while sid in existing_ids or sid in seen_ids:
            sid = f"{base_sid}-{n}"
            n += 1
        seen_ids.add(sid)

        label = Path(it.filename).stem.replace("_", " ").replace("-", " ")
        # humanize a bit
        label = re.sub(r"\s+", " ", label).strip()[:48]
        pattern = _build_pattern(it.filename, ver)
        snippet = _yaml_snippet(sid=sid, label=label, pattern=pattern)
        out.append(
            SuggestEntry(
                filename=it.filename,
                relpath=it.relpath,
                suggested_id=sid,
                label=label,
                pattern=pattern,
                version_guess=ver,
                yaml_snippet=snippet,
            )
        )
    return out


def format_suggestions(suggestions: list[SuggestEntry]) -> str:
    if not suggestions:
        return (
            "# No hay ISOs UNSUPPORTED en este volumen.\n"
            "# Todas las detectadas tienen entrada en catalog.yaml.\n"
        )
    lines = [
        "# Sugerencias generadas por: ventoy-iso-check suggest",
        "# Copia los bloques relevantes a catalog.yaml y ajusta page/resolver.",
        "#",
        f"# Total: {len(suggestions)}",
        "",
    ]
    for s in suggestions:
        lines.append(f"# --- {s.relpath} (version guess: {s.version_guess or '—'}) ---")
        lines.append(s.yaml_snippet.rstrip())
        lines.append("")
    return "\n".join(lines) + "\n"
