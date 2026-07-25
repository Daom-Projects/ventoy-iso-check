from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

import httpx

from ventoy_iso_check.models import CatalogEntry
from ventoy_iso_check.policy import (
    UpgradePolicy,
    hint_note,
    pick_target,
)

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
    policy: str | None = None


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


def _ubuntu_is_lts_label(raw_version: str, clean: str) -> bool:
    if "LTS" in raw_version.upper():
        return True
    # yy.04 series are LTS (24.04, 26.04, …)
    parts = clean.split(".")
    return len(parts) >= 2 and parts[1] == "04"


def _ubuntu_series(ver: str) -> str:
    parts = _ubuntu_clean_version(ver).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return ver


def resolve_ubuntu(
    entry: CatalogEntry,
    local_version: str | None,
    *,
    policy: UpgradePolicy = UpgradePolicy.LATEST_LTS,
    hint_newer: bool = False,
) -> ResolveResult:
    """Ubuntu meta-release with upgrade policy (latest / latest-lts / same-series)."""
    edition = (entry.edition or "desktop").lower()
    try:
        with _client() as client:
            r = client.get("https://changelogs.ubuntu.com/meta-release")
            r.raise_for_status()
            blocks = r.text.strip().split("\n\n")
            all_supported: list[str] = []
            lts_supported: list[str] = []
            for block in blocks:
                meta = {}
                for line in block.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
                raw = meta.get("Version")
                if not raw or meta.get("Supported") != "1":
                    continue
                clean = _ubuntu_clean_version(raw)
                all_supported.append(clean)
                if _ubuntu_is_lts_label(raw, clean):
                    lts_supported.append(clean)

            if not all_supported:
                return ResolveResult(error="No supported Ubuntu releases found")

            latest_any = _best_version(all_supported)
            latest_lts = _best_version(lts_supported) if lts_supported else latest_any

            series_best: str | None = None
            local_clean = _ubuntu_clean_version(local_version) if local_version else None
            local_series = _ubuntu_series(local_clean) if local_clean else None

            if local_series:
                series_matches = [
                    v
                    for v in all_supported
                    if v == local_series or v.startswith(local_series + ".")
                ]
                series_best = _best_version(series_matches)

            # Default semantics when policy is latest-lts:
            # live-server and LTS locals track LTS; interim tracks absolute latest.
            effective = policy
            if policy == UpgradePolicy.LATEST_LTS:
                local_is_lts = bool(
                    local_series and local_series.split(".")[-1:] == ["04"]
                )
                if edition != "live-server" and local_clean and not local_is_lts:
                    effective = UpgradePolicy.LATEST

            target = pick_target(
                policy=effective,
                series_best=series_best,
                latest_lts=latest_lts,
                absolute_latest=latest_any,
            )
            if not target:
                return ResolveResult(error="Could not determine Ubuntu version")

            series = _ubuntu_series(target)
            if edition == "live-server":
                fname = f"ubuntu-{target}-live-server-amd64.iso"
            else:
                fname = f"ubuntu-{target}-desktop-amd64.iso"
            url = f"https://releases.ubuntu.com/{series}/{fname}"
            head = client.head(url)
            if head.status_code >= 400:
                url_alt = f"https://releases.ubuntu.com/{target}/{fname}"
                if client.head(url_alt).status_code < 400:
                    url = url_alt

            notes: list[str] = []
            if series_best and series_best != target and policy != UpgradePolicy.SAME_SERIES:
                notes.append(
                    f"Serie local al día en {series_best}; objetivo ({policy.value}): {target}"
                )
            hn = hint_note(
                policy=policy,
                series_best=series_best,
                absolute_latest=latest_any,
                latest_lts=latest_lts,
                enabled=hint_newer,
            )
            if hn:
                notes.append(hn)
            notes.append(f"policy={policy.value}")

            return ResolveResult(
                latest_version=target,
                download_url=url,
                page=f"https://releases.ubuntu.com/{series}/",
                note="; ".join(notes) if notes else None,
                policy=policy.value,
            )
    except Exception as e:
        log.debug("ubuntu resolve failed: %s", e)
        return ResolveResult(error=str(e), page=entry.page)


def resolve_ubuntu_budgie(
    entry: CatalogEntry,
    local_version: str | None,
    *,
    policy: UpgradePolicy = UpgradePolicy.LATEST_LTS,
    hint_newer: bool = False,
) -> ResolveResult:
    """Ubuntu Budgie with upgrade policy."""
    try:
        with _client() as client:
            r = client.get("https://cdimage.ubuntu.com/ubuntu-budgie/releases/")
            r.raise_for_status()
            versions = _find_versions(r.text, r'href="(\d+\.\d+(?:\.\d+)?)/"')
            versions = [v for v in versions if not v.startswith("0")]
            absolute = _best_version(versions)
            if not absolute:
                return ResolveResult(error="No budgie releases found", page=entry.page)

            series_best = None
            if local_version:
                loc_series = _ubuntu_series(local_version)
                series_vers = [
                    v
                    for v in versions
                    if v == loc_series or v.startswith(loc_series + ".")
                ]
                series_best = _best_version(series_vers)

            # Treat .04 as LTS-like for budgie
            lts_like = [
                v
                for v in versions
                if len(v.split(".")) >= 2 and v.split(".")[1] == "04"
            ]
            latest_lts = _best_version(lts_like) or absolute

            target = pick_target(
                policy=policy,
                series_best=series_best,
                latest_lts=latest_lts,
                absolute_latest=absolute,
            ) or absolute

            series = _ubuntu_series(target)
            fname = f"ubuntu-budgie-{target}-desktop-amd64.iso"
            url = (
                f"https://cdimage.ubuntu.com/ubuntu-budgie/releases/"
                f"{target}/release/{fname}"
            )
            head = client.head(url)
            if head.status_code >= 400:
                url = (
                    f"https://cdimage.ubuntu.com/ubuntu-budgie/releases/"
                    f"{series}/release/{fname}"
                )
            notes: list[str] = []
            if series_best and series_best != target and policy != UpgradePolicy.SAME_SERIES:
                notes.append(
                    f"Serie local {series_best}; objetivo ({policy.value}): {target}"
                )
            hn = hint_note(
                policy=policy,
                series_best=series_best,
                absolute_latest=absolute,
                latest_lts=latest_lts,
                enabled=hint_newer,
            )
            if hn:
                notes.append(hn)
            notes.append(f"policy={policy.value}")
            return ResolveResult(
                latest_version=target,
                download_url=url,
                page=f"https://cdimage.ubuntu.com/ubuntu-budgie/releases/{target}/",
                note="; ".join(notes),
                policy=policy.value,
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_popos(
    entry: CatalogEntry,
    local_version: str | None,
    *,
    policy: UpgradePolicy = UpgradePolicy.LATEST_LTS,
    hint_newer: bool = False,
) -> ResolveResult:
    """Pop!_OS ISOs on iso.pop-os.org (no public dir listing; probe builds).

    Filename: pop-os_{series}_amd64_{flavor}_{build}.iso
    e.g. pop-os_24.04_amd64_nvidia_27.iso
    """
    flavor = (entry.edition or "nvidia").lower()
    if flavor not in ("nvidia", "intel", "generic"):
        flavor = "nvidia"

    # local_version may be "24.04", "24.04-nvidia-r27", or "24.04-r27"
    series = "24.04"
    local_build: int | None = None
    if local_version:
        m = re.match(
            r"(?P<series>\d+\.\d+)(?:-(?P<flavor>nvidia|intel|generic))?(?:-r(?P<build>\d+))?",
            local_version,
            flags=re.I,
        )
        if m:
            series = m.group("series")
            if m.group("build"):
                local_build = int(m.group("build"))
            if m.group("flavor"):
                flavor = m.group("flavor").lower()

    try:
        with _client() as client:
            # Prefer same series as local; also check a couple of known series.
            series_candidates = []
            for s in (series, "24.04", "22.04", "26.04"):
                if s not in series_candidates:
                    series_candidates.append(s)

            best: tuple[str, int, str] | None = None  # series, build, url
            for s in series_candidates:
                # Probe builds high→low; current nvidia tops around 27+
                for build in range(40, 0, -1):
                    fname = f"pop-os_{s}_amd64_{flavor}_{build}.iso"
                    url = f"https://iso.pop-os.org/{s}/amd64/{flavor}/{build}/{fname}"
                    try:
                        head = client.head(url)
                    except Exception:
                        continue
                    if head.status_code == 200:
                        best = (s, build, url)
                        break
                if best and s == series:
                    break  # found latest on local series; still allow newer series below

            # If a newer series has any build, prefer that series' best
            newer_series_best: tuple[str, int, str] | None = None
            for s in series_candidates:
                if s == series:
                    continue
                for build in range(40, 0, -1):
                    fname = f"pop-os_{s}_amd64_{flavor}_{build}.iso"
                    url = f"https://iso.pop-os.org/{s}/amd64/{flavor}/{build}/{fname}"
                    try:
                        head = client.head(url)
                    except Exception:
                        continue
                    if head.status_code == 200:
                        # only treat as newer if series version is higher
                        from packaging.version import InvalidVersion, Version

                        try:
                            if Version(s) > Version(series):
                                newer_series_best = (s, build, url)
                        except InvalidVersion:
                            pass
                        break

            series_best_t = best
            absolute_t = newer_series_best or best
            if policy == UpgradePolicy.SAME_SERIES:
                chosen = series_best_t or absolute_t
            else:
                chosen = absolute_t or series_best_t

            if not chosen:
                return ResolveResult(
                    error="No Pop!_OS ISO found via probe",
                    page=entry.page or "https://system76.com/pop/download/",
                )

            s, build, url = chosen
            latest = f"{s}-r{build}"
            notes: list[str] = []
            if local_build is not None and s == series and build == local_build:
                notes.append(f"Build actual {flavor} r{build}")
            elif local_build is not None and s == series and build > local_build:
                notes.append(f"Nuevo build {flavor}: r{local_build} → r{build}")
            if newer_series_best and policy != UpgradePolicy.SAME_SERIES:
                notes.append(f"Nueva serie Pop!_OS {newer_series_best[0]} disponible")
            if (
                policy == UpgradePolicy.SAME_SERIES
                and hint_newer
                and newer_series_best
                and series_best_t
            ):
                notes.append(
                    f"Serie local {series}-r{series_best_t[1]}; "
                    f"hay serie más nueva {newer_series_best[0]}-r{newer_series_best[1]} "
                    f"(ignorada por policy=same-series)"
                )
            notes.append(f"policy={policy.value}")

            return ResolveResult(
                latest_version=latest,
                download_url=url,
                page=entry.page or "https://system76.com/pop/download/",
                note="; ".join(notes),
                policy=policy.value,
            )
    except Exception as e:
        return ResolveResult(
            error=str(e),
            page=entry.page or "https://system76.com/pop/download/",
        )


def resolve_linuxmint(
    entry: CatalogEntry,
    local_version: str | None,
    *,
    policy: UpgradePolicy = UpgradePolicy.LATEST_LTS,
    hint_newer: bool = False,
) -> ResolveResult:
    """Linux Mint with upgrade policy (same-series = same major)."""
    edition = entry.edition or "cinnamon"
    try:
        with _client() as client:
            r = client.get("https://mirrors.kernel.org/linuxmint/stable/")
            r.raise_for_status()
            versions = _find_versions(r.text, r'href="(\d+(?:\.\d+)?)/"')
            absolute = _best_version(versions)
            if not absolute:
                return ResolveResult(error="No Mint versions", page=entry.page)

            series_best = None
            if local_version:
                major = local_version.split(".")[0]
                same = [
                    v for v in versions if v == major or v.startswith(major + ".")
                ]
                series_best = _best_version(same)

            # Mint has no separate LTS stream; latest-lts ≈ latest
            target = pick_target(
                policy=policy,
                series_best=series_best,
                latest_lts=absolute,
                absolute_latest=absolute,
            ) or absolute

            notes: list[str] = []
            if series_best and series_best != target and policy != UpgradePolicy.SAME_SERIES:
                notes.append(
                    f"Serie local {series_best}; objetivo ({policy.value}): {target}"
                )
            hn = hint_note(
                policy=policy,
                series_best=series_best,
                absolute_latest=absolute,
                latest_lts=absolute,
                enabled=hint_newer,
            )
            if hn:
                notes.append(hn)
            notes.append(f"policy={policy.value}")

            fname = f"linuxmint-{target}-{edition}-64bit.iso"
            url = f"https://mirrors.kernel.org/linuxmint/stable/{target}/{fname}"
            return ResolveResult(
                latest_version=target,
                download_url=url,
                page=entry.page,
                note="; ".join(notes),
                policy=policy.value,
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def _fedora_list_iso(
    client: httpx.Client,
    release: str,
    edition: str,
    arch: str,
) -> tuple[str | None, str | None, str | None]:
    """Return (version_token, download_url, error_note)."""
    if edition == "Silverblue":
        base = (
            f"https://dl.fedoraproject.org/pub/fedora/linux/releases/"
            f"{release}/Silverblue/{arch}/iso/"
        )
        sub = "Silverblue"
    else:
        base = (
            f"https://dl.fedoraproject.org/pub/fedora/linux/releases/"
            f"{release}/Workstation/{arch}/iso/"
        )
        sub = "Workstation"

    r2 = client.get(base)
    if r2.status_code >= 400:
        return None, None, f"No se pudo listar ISO {sub} en release {release}"

    if edition == "Silverblue":
        files = re.findall(
            r'href="(Fedora-Silverblue[^"]+\.iso)"',
            r2.text,
            flags=re.I,
        )
    else:
        files = re.findall(
            r'href="(Fedora-Workstation-Live[^"]+\.iso)"',
            r2.text,
            flags=re.I,
        )
    if not files:
        return None, None, f"Sin ISO {sub} en release {release}"

    fname = files[0]
    if edition == "Silverblue":
        m = re.search(
            r"(?:x86_64|aarch64)-(\d+-\d+(?:\.\d+)?)(?:\.iso)?$",
            fname,
            flags=re.I,
        )
        if not m:
            m = re.search(r"-(\d+-\d+(?:\.\d+)?)\.iso$", fname)
    else:
        m = re.search(
            r"Fedora-Workstation-Live-(?:x86_64-)?(\d+(?:-\d+(?:\.\d+)?)?)",
            fname,
            flags=re.I,
        )
        if not m:
            m = re.search(
                r"-(\d+-\d+(?:\.\d+)?)\.x86_64\.iso$", fname, flags=re.I
            )
    ver = m.group(1) if m else release
    return ver, base + fname, None


def resolve_fedora(
    entry: CatalogEntry,
    local_version: str | None,
    *,
    policy: UpgradePolicy = UpgradePolicy.LATEST_LTS,
    hint_newer: bool = False,
) -> ResolveResult:
    """Fedora with upgrade policy (same-series = same major number)."""
    edition = entry.edition or "Workstation"
    arch = entry.arch or "x86_64"
    try:
        with _client() as client:
            r = client.get(
                "https://dl.fedoraproject.org/pub/fedora/linux/releases/"
            )
            r.raise_for_status()
            releases = sorted(
                {
                    int(v)
                    for v in _find_versions(r.text, r'href="(\d+)/"')
                    if v.isdigit() and int(v) >= 30
                },
                reverse=True,
            )
            if not releases:
                return ResolveResult(error="No Fedora releases", page=entry.page)

            # Map release number → (ver, url) for available ISOs
            available: dict[str, tuple[str, str]] = {}
            for rel in releases[:8]:
                ver, url, _err = _fedora_list_iso(client, str(rel), edition, arch)
                if ver and url:
                    available[str(rel)] = (ver, url)

            if not available:
                return ResolveResult(
                    latest_version=str(releases[0]),
                    page=entry.page,
                    note="No ISO publicada en las releases recientes",
                )

            absolute_rel = max(available.keys(), key=int)
            absolute_ver, absolute_url = available[absolute_rel]

            local_major = None
            if local_version:
                local_major = local_version.split("-")[0].split(".")[0]

            series_ver = series_url = None
            if local_major and local_major in available:
                series_ver, series_url = available[local_major]
            elif local_major and local_major.isdigit():
                # try list that major even if not in top walk
                ver, url, _e = _fedora_list_iso(
                    client, local_major, edition, arch
                )
                if ver and url:
                    series_ver, series_url = ver, url
                    available[local_major] = (ver, url)

            target_ver = absolute_ver
            target_url = absolute_url
            if policy == UpgradePolicy.SAME_SERIES and series_ver:
                target_ver, target_url = series_ver, series_url
            # latest / latest-lts both mean newest Fedora major
            elif policy in (UpgradePolicy.LATEST, UpgradePolicy.LATEST_LTS):
                target_ver, target_url = absolute_ver, absolute_url

            notes: list[str] = []
            if (
                local_major
                and absolute_rel != local_major
                and policy != UpgradePolicy.SAME_SERIES
            ):
                notes.append(
                    f"Release local {local_major}; Fedora más nueva: {absolute_rel}"
                )
            if (
                policy == UpgradePolicy.SAME_SERIES
                and hint_newer
                and local_major
                and absolute_rel != local_major
            ):
                notes.append(
                    f"Serie local {local_major}; hay Fedora {absolute_rel} "
                    f"(ignorada por policy=same-series)"
                )
            notes.append(f"policy={policy.value}")

            return ResolveResult(
                latest_version=target_ver,
                download_url=target_url,
                page=entry.page,
                note="; ".join(notes),
                policy=policy.value,
            )

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
            for u in urls_to_try:
                r = client.get(u)
                if r.status_code >= 400:
                    continue
                found = re.findall(
                    r'(proxmox-ve[_-](\d+\.\d+-\d+)\.iso)', r.text, flags=re.I
                )
                if found:
                    matches = found
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


def resolve_elementary(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """elementary OS stable ISOs (filename often includes build date)."""
    try:
        with _client() as client:
            # Public download index / blog sometimes lists version; try direct builds path
            candidates = [
                "https://builds.elementary.io/",
                "https://elementary.io/",
            ]
            versions: list[str] = []
            files: list[tuple[str, str]] = []  # ver, url-ish
            for url in candidates:
                r = client.get(url)
                if r.status_code >= 400:
                    continue
                # elementaryos-8.1-stable-amd64.20260219.iso or elementaryos-8.0-...
                for m in re.finditer(
                    r"elementaryos-(\d+\.\d+)-stable-amd64(?:\.(\d{8}))?\.iso",
                    r.text,
                    flags=re.I,
                ):
                    ver = m.group(1)
                    if m.group(2):
                        ver = f"{m.group(1)}.{m.group(2)}"
                    versions.append(ver)
                    files.append((ver, m.group(0)))
            latest = _best_version(versions)
            if not latest:
                # Fallback: if local looks like 8.1, report page only
                return ResolveResult(
                    latest_version=local_version,
                    page=entry.page or "https://elementary.io/",
                    note="No se listó ISO en builds.elementary.io; verifica en elementary.io",
                )
            fname = None
            for ver, name in files:
                if ver == latest:
                    fname = name
                    break
            if not fname:
                # reconstruct without date if needed
                series = latest.split(".")[0] + "." + latest.split(".")[1]
                fname = f"elementaryos-{series}-stable-amd64.iso"
            # Common CDN pattern
            url = f"https://ams3.dl.elementary.io/download/{fname}"
            # Prefer builds host if listed
            head = client.head(url)
            if head.status_code >= 400:
                url = f"https://builds.elementary.io/{fname}"
            return ResolveResult(
                latest_version=latest,
                download_url=url,
                page=entry.page or "https://elementary.io/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_virtio_win(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Red Hat / Fedora VirtIO win drivers ISO (stable)."""
    base = (
        "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/"
        "stable-virtio/"
    )
    try:
        with _client() as client:
            r = client.get(base)
            r.raise_for_status()
            # virtio-win-0.1.285.iso or latest symlink
            matches = re.findall(
                r'href="(virtio-win-(\d+\.\d+\.\d+)\.iso)"', r.text, flags=re.I
            )
            if not matches:
                # latest stable often: virtio-win.iso redirect
                if "virtio-win.iso" in r.text:
                    return ResolveResult(
                        latest_version=local_version,
                        download_url=base + "virtio-win.iso",
                        page=entry.page or base,
                        note="Usar virtio-win.iso (stable) si no hay versión en el listado",
                    )
                return ResolveResult(
                    error="No virtio-win ISO en stable-virtio",
                    page=entry.page or base,
                )
            best = max(matches, key=lambda x: x[1])
            fname, ver = best
            return ResolveResult(
                latest_version=ver,
                download_url=base + fname,
                page=entry.page or base,
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_debian(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Debian amd64 netinst from cdimage.debian.org current."""
    arch = entry.arch or "amd64"
    try:
        with _client() as client:
            # current → redirects to versioned path
            base = f"https://cdimage.debian.org/debian-cd/current/{arch}/iso-cd/"
            r = client.get(base)
            r.raise_for_status()
            matches = re.findall(
                rf'href="(debian-(\d+(?:\.\d+)*)-{re.escape(arch)}-netinst\.iso)"',
                r.text,
                flags=re.I,
            )
            if not matches:
                return ResolveResult(
                    error="No debian netinst in current/",
                    page=entry.page,
                )
            # pick highest version
            best = max(matches, key=lambda x: x[1])
            fname, ver = best
            return ResolveResult(
                latest_version=ver,
                download_url=base + fname,
                page=entry.page or "https://www.debian.org/CD/http-ftp/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_archlinux(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Arch Linux monthly ISO."""
    try:
        with _client() as client:
            r = client.get("https://archlinux.org/download/")
            # mirrors.kernel.org listing is more scrape-friendly
            r2 = client.get("https://geo.mirror.pkgbuild.com/iso/latest/")
            text = r2.text if r2.status_code < 400 else r.text
            matches = re.findall(
                r"(archlinux-(\d{4}\.\d{2}\.\d{2})-x86_64\.iso)",
                text,
                flags=re.I,
            )
            if not matches:
                return ResolveResult(
                    error="No Arch ISO listed",
                    page=entry.page or "https://archlinux.org/download/",
                )
            best = max(matches, key=lambda x: x[1])
            fname, ver = best
            url = f"https://geo.mirror.pkgbuild.com/iso/latest/{fname}"
            return ResolveResult(
                latest_version=ver,
                download_url=url,
                page=entry.page or "https://archlinux.org/download/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_gparted(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """GParted Live from SourceForge stable."""
    try:
        with _client() as client:
            r = client.get(
                "https://sourceforge.net/projects/gparted/files/gparted-live-stable/"
            )
            r.raise_for_status()
            vers = _find_versions(r.text, r'href="[^"]*?/(\d+\.\d+\.\d+-\d+)/"')
            if not vers:
                vers = _find_versions(r.text, r"(\d+\.\d+\.\d+-\d+)")
            latest = _best_version(vers)
            if not latest:
                return ResolveResult(error="No GParted version", page=entry.page)
            fname = f"gparted-live-{latest}-amd64.iso"
            url = (
                f"https://sourceforge.net/projects/gparted/files/"
                f"gparted-live-stable/{latest}/{fname}/download"
            )
            return ResolveResult(
                latest_version=latest,
                download_url=url,
                page=entry.page or "https://gparted.org/download.php",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_memtest86plus(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Memtest86+ from GitHub releases."""
    try:
        with _client() as client:
            r = client.get(
                "https://api.github.com/repos/memtest86plus/memtest86plus/releases/latest"
            )
            r.raise_for_status()
            data = r.json()
            tag = (data.get("tag_name") or "").lstrip("v")
            url = None
            for a in data.get("assets") or []:
                name = a.get("name") or ""
                if name.endswith(".iso") and (
                    "64" in name or "x64" in name.lower() or "x86" in name
                ):
                    url = a.get("browser_download_url")
                    break
            if not url:
                for a in data.get("assets") or []:
                    if (a.get("name") or "").endswith(".iso"):
                        url = a.get("browser_download_url")
                        break
            return ResolveResult(
                latest_version=tag or None,
                download_url=url,
                page=entry.page or "https://www.memtest.org/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_pearos(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """pearOS — try GitHub releases; otherwise page only."""
    try:
        with _client() as client:
            # Common community repos / pages; best-effort
            for repo in (
                "PearOS/PearOS",
                "alainm23/pearOS",
            ):
                r = client.get(
                    f"https://api.github.com/repos/{repo}/releases/latest"
                )
                if r.status_code >= 400:
                    continue
                data = r.json()
                tag = (data.get("tag_name") or "").lstrip("v")
                url = None
                for a in data.get("assets") or []:
                    name = a.get("name") or ""
                    if "x86_64" in name and name.endswith(".iso"):
                        url = a.get("browser_download_url")
                        break
                if tag or url:
                    return ResolveResult(
                        latest_version=tag or local_version,
                        download_url=url,
                        page=entry.page or "https://pearos.xyz/",
                        note="Fuente GitHub community; verifica en pearos.xyz",
                    )
            return ResolveResult(
                latest_version=local_version,
                page=entry.page or "https://pearos.xyz/",
                note="Comprueba pearos.xyz / Discord del autor (sin API estable).",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_manjaro(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Manjaro official download page (xfce/kde/gnome)."""
    edition = (entry.edition or "xfce").lower()
    try:
        with _client() as client:
            r = client.get("https://manjaro.org/products/download/x86")
            text = r.text
            # full ISO links often on mirror: manjaro-...-x86_64.iso
            pat = rf'(https?://[^"\']*manjaro[-_]{re.escape(edition)}[^"\']*-(\d{{2}}(?:\.\d+)*)[^"\']*x86_64\.iso)'
            matches = re.findall(pat, text, flags=re.I)
            if not matches:
                pat2 = r'(https?://[^"\']+(manjaro[^"\']*-(\d{2}(?:\.\d+)*)[^"\']*x86_64\.iso))'
                matches = [(m[0], m[2]) for m in re.findall(pat2, text, flags=re.I) if edition in m[1].lower()]
            if not matches:
                return ResolveResult(
                    page=entry.page or "https://manjaro.org/download/",
                    note="No se listó ISO en la página; descarga manual en manjaro.org",
                )
            best = max(matches, key=lambda x: x[1])
            return ResolveResult(
                latest_version=best[1],
                download_url=best[0],
                page=entry.page or "https://manjaro.org/download/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_opensuse(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """openSUSE Leap (default) or Tumbleweed."""
    edition = (entry.edition or "leap").lower()
    try:
        with _client() as client:
            if edition == "tumbleweed":
                base = (
                    "https://download.opensuse.org/tumbleweed/iso/"
                )
                r = client.get(base)
                r.raise_for_status()
                # openSUSE-Tumbleweed-DVD-x86_64-SnapshotYYYYMMDD-Media.iso
                m = re.findall(
                    r'href="(openSUSE-Tumbleweed-DVD-x86_64-Snapshot(\d+)-Media\.iso)"',
                    r.text,
                    flags=re.I,
                )
                if not m:
                    m = re.findall(
                        r'href="(openSUSE-Tumbleweed-NET-x86_64-Snapshot(\d+)-Media\.iso)"',
                        r.text,
                        flags=re.I,
                    )
                if not m:
                    return ResolveResult(error="No Tumbleweed ISO", page=entry.page)
                best = max(m, key=lambda x: x[1])
                return ResolveResult(
                    latest_version=best[1],
                    download_url=base + best[0],
                    page=entry.page or "https://get.opensuse.org/tumbleweed/",
                )
            # Leap: discover current minor from distribution/leap/
            r = client.get("https://download.opensuse.org/distribution/leap/")
            r.raise_for_status()
            leaps = re.findall(r'href="(\d+\.\d+)/"', r.text)
            leaps = sorted({x for x in leaps if not x.startswith("0")}, key=lambda v: [int(p) for p in v.split(".")])
            if not leaps:
                return ResolveResult(error="No Leap versions listed", page=entry.page)
            ver = leaps[-1]
            base = f"https://download.opensuse.org/distribution/leap/{ver}/iso/"
            r2 = client.get(base)
            r2.raise_for_status()
            # openSUSE-Leap-15.6-DVD-x86_64-Media.iso or Build…
            m = re.findall(
                rf'href="(openSUSE-Leap-{re.escape(ver)}-DVD-x86_64[^"]*\.iso)"',
                r2.text,
                flags=re.I,
            )
            if not m:
                m = re.findall(
                    rf'href="(openSUSE-Leap-{re.escape(ver)}-NET-x86_64[^"]*\.iso)"',
                    r2.text,
                    flags=re.I,
                )
            if not m:
                return ResolveResult(
                    latest_version=ver,
                    page=entry.page or base,
                    note="Versión Leap detectada; ISO no listada en iso/",
                )
            fname = sorted(m)[-1]
            return ResolveResult(
                latest_version=ver,
                download_url=base + fname,
                page=entry.page or "https://get.opensuse.org/leap/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_rocky(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Rocky Linux DVD/minimal from download.rockylinux.org."""
    arch = entry.arch or "x86_64"
    try:
        with _client() as client:
            r = client.get("https://download.rockylinux.org/pub/rocky/")
            r.raise_for_status()
            majors = re.findall(r'href="(\d+)/"', r.text)
            majors = sorted({int(m) for m in majors if m.isdigit()})
            if not majors:
                return ResolveResult(error="No Rocky major versions", page=entry.page)
            major = majors[-1]
            base = f"https://download.rockylinux.org/pub/rocky/{major}/isos/{arch}/"
            r2 = client.get(base)
            r2.raise_for_status()
            # Rocky-9.5-x86_64-dvd.iso or minimal
            kind = "minimal" if (entry.edition or "").lower() == "minimal" else "dvd"
            matches = re.findall(
                rf'href="(Rocky-(\d+(?:\.\d+)*)-{re.escape(arch)}-{kind}\.iso)"',
                r2.text,
                flags=re.I,
            )
            if not matches:
                matches = re.findall(
                    rf'href="(Rocky-(\d+(?:\.\d+)*)-{re.escape(arch)}-dvd\.iso)"',
                    r2.text,
                    flags=re.I,
                )
            if not matches:
                return ResolveResult(
                    latest_version=str(major),
                    page=entry.page or base,
                    note="Directorio de ISOs sin coincidencia dvd/minimal",
                )
            best = max(matches, key=lambda x: x[1])
            return ResolveResult(
                latest_version=best[1],
                download_url=base + best[0],
                page=entry.page or "https://rockylinux.org/download",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_almalinux(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """AlmaLinux ISO listing."""
    arch = entry.arch or "x86_64"
    try:
        with _client() as client:
            r = client.get("https://repo.almalinux.org/almalinux/")
            r.raise_for_status()
            majors = re.findall(r'href="(\d+)/"', r.text)
            majors = sorted({int(m) for m in majors if m.isdigit()})
            if not majors:
                return ResolveResult(error="No Alma major", page=entry.page)
            major = majors[-1]
            base = f"https://repo.almalinux.org/almalinux/{major}/isos/{arch}/"
            r2 = client.get(base)
            r2.raise_for_status()
            kind = "minimal" if (entry.edition or "").lower() == "minimal" else "dvd"
            matches = re.findall(
                rf'href="(AlmaLinux-(\d+(?:\.\d+)*)-{re.escape(arch)}-{kind}\.iso)"',
                r2.text,
                flags=re.I,
            )
            if not matches:
                matches = re.findall(
                    rf'href="(AlmaLinux-(\d+(?:\.\d+)*)-{re.escape(arch)}-dvd\.iso)"',
                    r2.text,
                    flags=re.I,
                )
            if not matches:
                return ResolveResult(
                    latest_version=str(major),
                    page=entry.page or base,
                    note="Sin ISO dvd/minimal listada",
                )
            best = max(matches, key=lambda x: x[1])
            return ResolveResult(
                latest_version=best[1],
                download_url=base + best[0],
                page=entry.page or "https://almalinux.org/get-almalinux/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_alpine(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Alpine standard ISO (latest-stable)."""
    arch = entry.arch or "x86_64"
    try:
        with _client() as client:
            base = f"https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/{arch}/"
            r = client.get(base)
            r.raise_for_status()
            matches = re.findall(
                rf'href="(alpine-standard-(\d+\.\d+(?:\.\d+)*)-{re.escape(arch)}\.iso)"',
                r.text,
                flags=re.I,
            )
            if not matches:
                matches = re.findall(
                    rf'href="(alpine-extended-(\d+\.\d+(?:\.\d+)*)-{re.escape(arch)}\.iso)"',
                    r.text,
                    flags=re.I,
                )
            if not matches:
                return ResolveResult(error="No Alpine ISO", page=entry.page or base)
            best = max(matches, key=lambda x: x[1])
            return ResolveResult(
                latest_version=best[1],
                download_url=base + best[0],
                page=entry.page or "https://alpinelinux.org/downloads/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_mxlinux(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """MX Linux from SourceForge."""
    try:
        with _client() as client:
            r = client.get("https://sourceforge.net/projects/mx-linux/files/Final/")
            r.raise_for_status()
            # MX-23.x_x64.iso style under Final/MX-XX/
            vers = re.findall(r'href="[^"]*?MX[-_]?(\d+(?:\.\d+)*)', r.text, flags=re.I)
            latest = _best_version(vers) if vers else None
            # Also try direct listing of iso names
            isos = re.findall(
                r"(MX[-_](\d+(?:\.\d+)*)[^\"']*_x64\.iso)",
                r.text,
                flags=re.I,
            )
            if isos:
                best = max(isos, key=lambda x: x[1])
                fname, ver = best
                url = (
                    "https://sourceforge.net/projects/mx-linux/files/Final/"
                    f"{fname}/download"
                )
                return ResolveResult(
                    latest_version=ver,
                    download_url=url,
                    page=entry.page or "https://mxlinux.org/download-links/",
                )
            return ResolveResult(
                latest_version=latest,
                page=entry.page or "https://mxlinux.org/download-links/",
                note="Consulta la web de MX para el mirror más cercano",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_supergrub2(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Super Grub2 Disk from GitHub releases."""
    try:
        with _client() as client:
            r = client.get(
                "https://api.github.com/repos/supergrub/supergrub/releases/latest"
            )
            r.raise_for_status()
            data = r.json()
            tag = (data.get("tag_name") or "").lstrip("v")
            url = None
            for a in data.get("assets") or []:
                name = (a.get("name") or "").lower()
                if name.endswith(".iso") and ("x86_64" in name or "hybrid" in name or "multiarch" in name):
                    url = a.get("browser_download_url")
                    break
            if not url:
                for a in data.get("assets") or []:
                    if (a.get("name") or "").lower().endswith(".iso"):
                        url = a.get("browser_download_url")
                        break
            return ResolveResult(
                latest_version=tag or None,
                download_url=url,
                page=entry.page or "https://www.supergrubdisk.org/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_kubuntu(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Kubuntu desktop from cdimage.ubuntu.com (LTS-aware via ubuntu-like scrape)."""
    arch = entry.arch or "amd64"
    try:
        with _client() as client:
            base = "https://cdimage.ubuntu.com/kubuntu/releases/"
            r = client.get(base)
            r.raise_for_status()
            vers = re.findall(r'href="(\d+\.\d+(?:\.\d+)?)/"', r.text)
            # Prefer even.04 LTS-style
            lts = [v for v in vers if re.match(r"^\d+\.04", v)]
            pool = lts or vers
            if not pool:
                return ResolveResult(error="No Kubuntu releases", page=entry.page)
            best_series = _best_version(pool)
            if not best_series:
                return ResolveResult(error="No Kubuntu version", page=entry.page)
            page = f"{base}{best_series}/release/"
            r2 = client.get(page)
            r2.raise_for_status()
            m = re.findall(
                rf'href="(kubuntu-({re.escape(best_series)}(?:\.\d+)?)-desktop-{re.escape(arch)}\.iso)"',
                r2.text,
                flags=re.I,
            )
            if not m:
                # try without nested version group
                m2 = re.findall(
                    rf'href="(kubuntu-(\d+\.\d+(?:\.\d+)?)-desktop-{re.escape(arch)}\.iso)"',
                    r2.text,
                    flags=re.I,
                )
                m = m2
            if not m:
                return ResolveResult(
                    latest_version=best_series,
                    page=entry.page or page,
                    note="Serie detectada; ISO no listada en release/",
                )
            fname, ver = max(m, key=lambda x: x[1])
            return ResolveResult(
                latest_version=ver,
                download_url=page + fname,
                page=entry.page or "https://kubuntu.org/getkubuntu/",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


def resolve_garuda(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    """Garuda Linux ISO list (best-effort from downloads page)."""
    edition = (entry.edition or "dr460nized").lower()
    try:
        with _client() as client:
            r = client.get("https://garudalinux.org/downloads")
            text = r.text
            # full URLs with date stamp
            all_isos = re.findall(
                r'(https?://[^\s"\']+garuda[^\s"\']*-(\d{8})[^\s"\']*\.iso)',
                text,
                flags=re.I,
            )
            matches = [m for m in all_isos if edition in m[0].lower()]
            if not matches:
                matches = all_isos
            if not matches:
                return ResolveResult(
                    page=entry.page or "https://garudalinux.org/downloads",
                    note="Descarga manual en garudalinux.org (ediciones múltiples)",
                )
            best = max(matches, key=lambda x: x[1])
            return ResolveResult(
                latest_version=best[1],
                download_url=best[0],
                page=entry.page or "https://garudalinux.org/downloads",
            )
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page)


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
    "popos": resolve_popos,
    "elementary": resolve_elementary,
    "virtio_win": resolve_virtio_win,
    "debian": resolve_debian,
    "archlinux": resolve_archlinux,
    "gparted": resolve_gparted,
    "memtest86plus": resolve_memtest86plus,
    "pearos": resolve_pearos,
    "manjaro": resolve_manjaro,
    "opensuse": resolve_opensuse,
    "rocky": resolve_rocky,
    "almalinux": resolve_almalinux,
    "alpine": resolve_alpine,
    "mxlinux": resolve_mxlinux,
    "supergrub2": resolve_supergrub2,
    "kubuntu": resolve_kubuntu,
    "garuda": resolve_garuda,
    "none": lambda e, v: ResolveResult(page=e.page, note=e.note),
}


@lru_cache(maxsize=64)
def resolve_cached(resolver_name: str, entry_id: str, local_version: str | None) -> ResolveResult:
    # lru_cache needs hashable args; entry looked up by caller
    raise NotImplementedError


def resolve(
    entry: CatalogEntry,
    local_version: str | None,
    *,
    policy: UpgradePolicy | str = UpgradePolicy.LATEST_LTS,
    hint_newer: bool = False,
) -> ResolveResult:
    if isinstance(policy, str):
        policy = UpgradePolicy.parse(policy)
    fn = RESOLVERS.get(entry.resolver or "none")
    if not fn:
        return ResolveResult(
            page=entry.page,
            note=entry.note or f"Resolver desconocido: {entry.resolver}",
        )
    try:
        from ventoy_iso_check.policy import POLICY_AWARE_RESOLVERS

        if (entry.resolver or "none") in POLICY_AWARE_RESOLVERS:
            result = fn(
                entry,
                local_version,
                policy=policy,
                hint_newer=hint_newer,
            )
        else:
            result = fn(entry, local_version)
    except Exception as e:
        return ResolveResult(error=str(e), page=entry.page, note=entry.note)
    if entry.page and not result.page:
        result.page = entry.page
    if entry.note and not result.note:
        result.note = entry.note
    if result.policy is None:
        result.policy = policy.value
    return result
