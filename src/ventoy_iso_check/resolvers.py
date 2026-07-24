from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

import httpx

from ventoy_iso_check.models import CatalogEntry

log = logging.getLogger(__name__)

USER_AGENT = "ventoy-iso-check/0.1 (+https://github.com/local/ventoy-iso-check)"
TIMEOUT = 25.0


@dataclass
class ResolveResult:
    latest_version: str | None = None
    download_url: str | None = None
    page: str | None = None
    note: str | None = None
    error: str | None = None


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=TIMEOUT,
    )


def _find_versions(text: str, pattern: str) -> list[str]:
    return list(dict.fromkeys(re.findall(pattern, text)))


def _best_version(versions: list[str]) -> str | None:
    if not versions:
        return None
    from packaging.version import InvalidVersion, Version

    def key(v: str):
        try:
            return Version(v.replace("-", "."))
        except InvalidVersion:
            return Version("0")

    return sorted(versions, key=key)[-1]


def _ubuntu_clean_version(ver: str) -> str:
    return ver.replace(" LTS", "").replace("LTS", "").strip()


def resolve_ubuntu(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Use Ubuntu meta-release; prefer same series as the local ISO when possible."""
    edition = (entry.edition or "desktop").lower()
    try:
        with _client() as client:
            r = client.get("https://changelogs.ubuntu.com/meta-release")
            r.raise_for_status()
            blocks = r.text.strip().split("\n\n")
            candidates: list[str] = []
            for block in blocks:
                meta = {}
                for line in block.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
                ver = meta.get("Version")
                if not ver:
                    continue
                if meta.get("Supported") == "1":
                    candidates.append(_ubuntu_clean_version(ver))

            if not candidates:
                return ResolveResult(error="No supported Ubuntu releases found")

            latest: str | None = None
            if local_version:
                local_clean = _ubuntu_clean_version(local_version)
                series = ".".join(local_clean.split(".")[:2])  # 24.04 or 25.10
                series_matches = [
                    v for v in candidates if v == series or v.startswith(series + ".")
                ]
                if series_matches:
                    latest = _best_version(series_matches)

            if not latest:
                # No same-series match: report highest supported (may be a jump)
                latest = _best_version(candidates)

            if not latest:
                return ResolveResult(error="Could not determine Ubuntu version")

            series = ".".join(latest.split(".")[:2])
            if edition == "live-server":
                fname = f"ubuntu-{latest}-live-server-amd64.iso"
            else:
                fname = f"ubuntu-{latest}-desktop-amd64.iso"
            url = f"https://releases.ubuntu.com/{series}/{fname}"
            head = client.head(url)
            if head.status_code >= 400:
                url_alt = f"https://releases.ubuntu.com/{latest}/{fname}"
                if client.head(url_alt).status_code < 400:
                    url = url_alt
            return ResolveResult(
                latest_version=latest,
                download_url=url,
                page=f"https://releases.ubuntu.com/{series}/",
            )
    except Exception as e:
        log.debug("ubuntu resolve failed: %s", e)
        return ResolveResult(error=str(e), page=entry.page)


def resolve_ubuntu_budgie(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    try:
        with _client() as client:
            r = client.get("https://cdimage.ubuntu.com/ubuntu-budgie/releases/")
            r.raise_for_status()
            versions = _find_versions(r.text, r'href="(\d+\.\d+(?:\.\d+)?)/"')
            # filter out junk
            versions = [v for v in versions if not v.startswith("0")]
            latest = _best_version(versions)
            if not latest:
                return ResolveResult(error="No budgie releases found", page=entry.page)
            series = ".".join(latest.split(".")[:2])
            # Prefer local series point-release if possible
            if local_version:
                loc_series = ".".join(local_version.split(".")[:2])
                series_vers = [v for v in versions if v.startswith(loc_series)]
                if series_vers:
                    latest = _best_version(series_vers) or latest
                    series = loc_series
            fname = f"ubuntu-budgie-{latest}-desktop-amd64.iso"
            url = (
                f"https://cdimage.ubuntu.com/ubuntu-budgie/releases/"
                f"{latest}/release/{fname}"
            )
            # sometimes path uses series only
            head = client.head(url)
            if head.status_code >= 400:
                url = (
                    f"https://cdimage.ubuntu.com/ubuntu-budgie/releases/"
                    f"{series}/release/{fname}"
                )
            return ResolveResult(
                latest_version=latest,
                download_url=url,
                page=f"https://cdimage.ubuntu.com/ubuntu-budgie/releases/{latest}/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_linuxmint(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    edition = entry.edition or "cinnamon"
    try:
        with _client() as client:
            # Directory listing of stable releases
            r = client.get("https://mirrors.kernel.org/linuxmint/stable/")
            r.raise_for_status()
            versions = _find_versions(r.text, r'href="(\d+(?:\.\d+)?)/"')
            latest = _best_version(versions)
            if not latest:
                return ResolveResult(error="No Mint versions", page=entry.page)
            if local_version:
                major = local_version.split(".")[0]
                same = [v for v in versions if v == major or v.startswith(major + ".")]
                if same:
                    latest = _best_version(same) or latest
            fname = f"linuxmint-{latest}-{edition}-64bit.iso"
            url = f"https://mirrors.kernel.org/linuxmint/stable/{latest}/{fname}"
            return ResolveResult(
                latest_version=latest,
                download_url=url,
                page=entry.page,
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_fedora(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    edition = entry.edition or "Workstation"
    arch = entry.arch or "x86_64"
    try:
        with _client() as client:
            r = client.get(
                "https://dl.fedoraproject.org/pub/fedora/linux/releases/"
            )
            r.raise_for_status()
            # numeric release dirs only
            releases = [
                v
                for v in _find_versions(r.text, r'href="(\d+)/"')
                if v.isdigit() and int(v) >= 30
            ]
            latest_rel = max(releases, key=int) if releases else None
            if not latest_rel:
                return ResolveResult(error="No Fedora releases", page=entry.page)

            # Prefer matching major of local if still listed
            if local_version:
                major = local_version.split("-")[0].split(".")[0]
                if major in releases:
                    latest_rel = major

            if edition == "Silverblue":
                base = (
                    f"https://dl.fedoraproject.org/pub/fedora/linux/releases/"
                    f"{latest_rel}/Silverblue/{arch}/iso/"
                )
                r2 = client.get(base)
                if r2.status_code >= 400:
                    return ResolveResult(
                        latest_version=latest_rel,
                        page=entry.page,
                        note="No se pudo listar ISO Silverblue",
                    )
                files = re.findall(
                    r'href="(Fedora-Silverblue[^"]+\.iso)"',
                    r2.text,
                    flags=re.I,
                )
                if files:
                    fname = files[0]
                    # Prefer ...-43-1.6.iso or ...-x86_64-43-1.6.iso (avoid matching x86)
                    m = re.search(
                        r"(?:x86_64|aarch64)-(\d+-\d+(?:\.\d+)?)(?:\.iso)?$",
                        fname,
                        flags=re.I,
                    )
                    if not m:
                        m = re.search(r"-(\d+-\d+(?:\.\d+)?)\.iso$", fname)
                    ver = m.group(1) if m else f"{latest_rel}"
                    return ResolveResult(
                        latest_version=ver,
                        download_url=base + fname,
                        page=entry.page,
                    )
            else:
                base = (
                    f"https://dl.fedoraproject.org/pub/fedora/linux/releases/"
                    f"{latest_rel}/Workstation/{arch}/iso/"
                )
                r2 = client.get(base)
                r2.raise_for_status()
                files = re.findall(
                    r'href="(Fedora-Workstation-Live[^"]+\.iso)"',
                    r2.text,
                    flags=re.I,
                )
                if files:
                    fname = files[0]
                    m = re.search(
                        r"Fedora-Workstation-Live-(?:x86_64-)?(\d+(?:-\d+(?:\.\d+)?)?)",
                        fname,
                        flags=re.I,
                    )
                    if not m:
                        m = re.search(
                            r"-(\d+-\d+(?:\.\d+)?)\.x86_64\.iso$", fname, flags=re.I
                        )
                    ver = m.group(1) if m else latest_rel
                    return ResolveResult(
                        latest_version=ver,
                        download_url=base + fname,
                        page=entry.page,
                    )
            return ResolveResult(latest_version=latest_rel, page=entry.page)

    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_kali(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    edition = entry.edition or "installer"
    arch = entry.arch or "amd64"
    try:
        with _client() as client:
            r = client.get("https://cdimage.kali.org/current/")
            r.raise_for_status()
            pattern = (
                rf'href="(kali-linux-(\d+\.\d+)-{re.escape(edition)}-'
                rf'{re.escape(arch)}\.iso)"'
            )
            matches = re.findall(pattern, r.text)
            if not matches:
                # broader
                matches = re.findall(
                    rf'href="(kali-linux-(\d+\.\d+)-[^"]+{re.escape(arch)}\.iso)"',
                    r.text,
                )
            if not matches:
                return ResolveResult(error="No Kali ISO in current/", page=entry.page)
            fname, ver = matches[0]
            url = f"https://cdimage.kali.org/current/{fname}"
            return ResolveResult(latest_version=ver, download_url=url, page=entry.page)
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_systemrescue(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    try:
        with _client() as client:
            # GitLab or sourceforge — use official download page + pattern
            r = client.get("https://www.system-rescue.org/Download/")
            r.raise_for_status()
            vers = _find_versions(r.text, r"systemrescue-(\d+\.\d+)-amd64\.iso")
            latest = _best_version(vers)
            if not latest:
                # try sourceforge RSS-ish listing
                r2 = client.get(
                    "https://sourceforge.net/projects/systemrescuecd/files/sysresccd-x86/"
                )
                if r2.status_code < 400:
                    vers = _find_versions(r2.text, r"(\d+\.\d+)/")
                    latest = _best_version(vers)
            if not latest:
                return ResolveResult(error="No SystemRescue version", page=entry.page)
            fname = f"systemrescue-{latest}-amd64.iso"
            url = (
                f"https://sourceforge.net/projects/systemrescuecd/files/"
                f"sysresccd-x86/{latest}/{fname}/download"
            )
            return ResolveResult(
                latest_version=latest, download_url=url, page=entry.page
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_clonezilla(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    try:
        with _client() as client:
            r = client.get(
                "https://sourceforge.net/projects/clonezilla/files/clonezilla_live_stable/"
            )
            r.raise_for_status()
            vers = _find_versions(r.text, r'href="[^"]*?/(\d+\.\d+\.\d+-\d+)/"')
            if not vers:
                vers = _find_versions(r.text, r"(\d+\.\d+\.\d+-\d+)")
            latest = _best_version(vers)
            if not latest:
                return ResolveResult(error="No Clonezilla version", page=entry.page)
            fname = f"clonezilla-live-{latest}-amd64.iso"
            url = (
                f"https://sourceforge.net/projects/clonezilla/files/"
                f"clonezilla_live_stable/{latest}/{fname}/download"
            )
            return ResolveResult(
                latest_version=latest, download_url=url, page=entry.page
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_rescuezilla(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    try:
        with _client() as client:
            r = client.get(
                "https://api.github.com/repos/rescuezilla/rescuezilla/releases/latest"
            )
            r.raise_for_status()
            data = r.json()
            tag = (data.get("tag_name") or "").lstrip("v")
            assets = data.get("assets") or []
            url = None
            for a in assets:
                name = a.get("name") or ""
                if name.endswith(".iso") and "64bit" in name:
                    url = a.get("browser_download_url")
                    break
            return ResolveResult(
                latest_version=tag or None,
                download_url=url,
                page="https://github.com/rescuezilla/rescuezilla/releases/latest",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_proxmox(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    urls_to_try = [
        "https://enterprise.proxmox.com/iso/",
        "http://download.proxmox.com/iso/",
        "https://www.proxmox.com/en/downloads/proxmox-virtual-environment/iso",
    ]
    try:
        with _client() as client:
            matches: list[tuple[str, str]] = []
            base_url = urls_to_try[0]
            for u in urls_to_try:
                r = client.get(u)
                if r.status_code >= 400:
                    continue
                found = re.findall(
                    r'(proxmox-ve[_-](\d+\.\d+-\d+)\.iso)', r.text, flags=re.I
                )
                if found:
                    matches = found
                    base_url = u if u.endswith("/") else u.rsplit("/", 1)[0] + "/"
                    # normalize base for enterprise/download hosts
                    if "download.proxmox.com" in u or "enterprise.proxmox.com" in u:
                        base_url = u if u.endswith("/") else u + "/"
                    break
            if not matches:
                return ResolveResult(
                    error="No Proxmox ISO listed",
                    page=entry.page,
                    note="Comprueba https://www.proxmox.com/en/downloads",
                )
            best = max(matches, key=lambda x: x[1].replace("-", "."))
            fname, ver = best
            if not fname.endswith(".iso"):
                fname = fname  # already full from group
            # Prefer public download host when possible
            url = f"http://download.proxmox.com/iso/{fname}"
            head = client.head(url)
            if head.status_code >= 400:
                url = f"https://enterprise.proxmox.com/iso/{fname}"
            return ResolveResult(
                latest_version=ver, download_url=url, page=entry.page
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_tails(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    try:
        with _client() as client:
            r = client.get("https://tails.net/install/download/")
            # may redirect / block scrapers — try JSON API style mirrors
            if r.status_code >= 400:
                r = client.get("https://mirrors.edge.kernel.org/tails/stable/")
            text = r.text
            vers = _find_versions(text, r"tails-amd64-(\d+(?:\.\d+)*)")
            latest = _best_version(vers)
            if not latest:
                # fallback: github-like
                r2 = client.get("https://tails.net/latest.yml")
                if r2.status_code < 400:
                    m = re.search(r"version:\s*['\"]?(\d+(?:\.\d+)*)", r2.text)
                    if m:
                        latest = m.group(1)
            if not latest:
                return ResolveResult(
                    error="No Tails version detected",
                    page=entry.page,
                    note="Abre la página de descarga de Tails",
                )
            fname = f"tails-amd64-{latest}.img"
            url = f"https://download.tails.net/tails/stable/tails-amd64-{latest}/{fname}"
            return ResolveResult(
                latest_version=latest, download_url=url, page=entry.page
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_cachyos(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    try:
        with _client() as client:
            # CachyOS ISO names use YYMMDD
            r = client.get("https://cdn77.cachyos.org/ISO/desktop/")
            if r.status_code >= 400:
                r = client.get("https://mirror.cachyos.org/ISO/desktop/")
            r.raise_for_status()
            dates = _find_versions(r.text, r"cachyos-desktop-linux-(\d{6})\.iso")
            if not dates:
                dates = _find_versions(r.text, r'href="(\d{6})/"')
            latest = max(dates) if dates else None
            if not latest:
                return ResolveResult(error="No CachyOS ISO", page=entry.page)
            fname = f"cachyos-desktop-linux-{latest}.iso"
            # try common CDN path
            url = f"https://cdn77.cachyos.org/ISO/desktop/{latest}/{fname}"
            head = client.head(url)
            if head.status_code >= 400:
                url = f"https://cdn77.cachyos.org/ISO/desktop/{fname}"
            return ResolveResult(
                latest_version=latest, download_url=url, page=entry.page
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_hirens(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    try:
        with _client() as client:
            r = client.get("https://www.hirensbootcd.org/download/")
            r.raise_for_status()
            vers = _find_versions(r.text, r"HBCD_PE_?(\d+(?:\.\d+)*)")
            latest = _best_version(vers) if vers else None
            # often just "Hiren's BootCD PE x64"
            url_m = re.search(r'href="(https?://[^"]+HBCD[^"]+\.iso)"', r.text, re.I)
            url = url_m.group(1) if url_m else None
            return ResolveResult(
                latest_version=latest,
                download_url=url,
                page=entry.page,
                note="Comprobar en hirensbootcd.org si la URL directa no aparece",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_zorin(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    # Zorin uses gated CDN downloads; only report page
    return ResolveResult(
        latest_version=None,
        page=entry.page or "https://zorin.com/os/download/",
        note="Descarga manual desde zorin.com (CDN con token). Compara el número de versión del nombre del archivo.",
    )


RESOLVERS = {
    "ubuntu": resolve_ubuntu,
    "ubuntu_budgie": resolve_ubuntu_budgie,
    "linuxmint": resolve_linuxmint,
    "fedora": resolve_fedora,
    "kali": resolve_kali,
    "systemrescue": resolve_systemrescue,
    "clonezilla": resolve_clonezilla,
    "rescuezilla": resolve_rescuezilla,
    "proxmox": resolve_proxmox,
    "tails": resolve_tails,
    "cachyos": resolve_cachyos,
    "hirens": resolve_hirens,
    "zorin": resolve_zorin,
    "none": lambda e, v: ResolveResult(page=e.page, note=e.note),
}


@lru_cache(maxsize=64)
def resolve_cached(resolver_name: str, entry_id: str, local_version: str | None) -> ResolveResult:
    # lru_cache needs hashable args; entry looked up by caller
    raise NotImplementedError


def resolve(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    fn = RESOLVERS.get(entry.resolver or "none")
    if not fn:
        return ResolveResult(page=entry.page, note=entry.note or f"Resolver desconocido: {entry.resolver}")
    try:
        result = fn(entry, local_version)
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page, note=entry.note)
    if entry.page and not result.page:
        result.page = entry.page
    if entry.note and not result.note:
        result.note = entry.note
    return result
