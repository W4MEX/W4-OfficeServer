# SPDX-FileCopyrightText: 2026 W4
# SPDX-License-Identifier: AGPL-3.0-only
"""Compare the four W4 repositories and their pinned components with GitHub."""

import base64
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import subprocess
import sys

FORKS = {
    "W4-OfficeServer": "DocumentServer",
    "W4-OfficeDesktop": "DesktopEditors",
    "W4-Office-WebApps": "web-apps",
    "W4-DesktopApps": "desktop-apps",
}
W4_PINS = {
    "web-apps": "W4MEX/W4-Office-WebApps",
    "desktop-apps": "W4MEX/W4-DesktopApps",
}
UPSTREAM_PINS = {
    "core", "core-fonts", "desktop-sdk", "dictionaries", "document-formats",
    "document-server-integration", "document-server-package", "document-templates",
    "sdkjs", "sdkjs-forms", "server",
}
APPROVED_ARTWORK = {
    "web-apps": (
        "f184b698775a1922db0ca99aec8e8ab57c1cf592",
        (
            "theme/w4-office/assets/img/header/w4-office-blue.svg",
            "theme/w4-office/assets/img/header/w4-office-white.svg",
        ),
    ),
    "desktop-apps": (
        "82ac2abb9d0e0f6abd43f9853569b6ef87fe793f",
        ("win-linux/res/icons/w4-office.ico",),
    ),
}


def api(endpoint):
    return json.loads(subprocess.check_output(
        [os.environ.get("W4_GH", "gh"), "api", endpoint], text=True, encoding="utf-8"
    ))


@lru_cache
def tip(repo):
    commit = api(f"repos/{repo}/commits/main")
    return commit["sha"], commit["commit"]["tree"]["sha"]


def content(repo, ref, path):
    result = api(f"repos/{repo}/contents/{path}?ref={ref}")
    return base64.b64decode(result["content"], validate=False)


def comparison(repo, base, head):
    return api(f"repos/{repo}/compare/{base}...{head}?per_page=1")


def link(repo, sha):
    return f"[`{sha[:7]}`](https://github.com/{repo}/commit/{sha})"


def module_url(config, path):
    return subprocess.check_output(
        ["git", "config", "--file", "-", "--get", f"submodule.{path}.url"],
        input=config,
    ).decode("utf-8").strip()


def audit():
    lines = [
        "# Actualizaciones de Euro-Office para W4",
        "",
        "Informe de revisión. Las revisiones candidatas deben probarse antes de integrarse.",
        "",
        "| Fork W4 | Actual | Euro-Office | Commits entrantes |",
        "|---|---|---|---:|",
    ]
    for name, parent in FORKS.items():
        w4, upstream = f"W4MEX/{name}", f"Euro-Office/{parent}"
        current, _ = tip(w4)
        candidate, _ = tip(upstream)
        status = comparison(upstream, candidate, f"W4MEX:{current}")
        lines.append(
            f"| {name} | {link(w4, current)} | {link(upstream, candidate)} | {status['behind_by']} |"
        )

    lines.extend([
        "", "## Submódulos de Server y Desktop", "",
        "| Producto | Componente | Revisión fijada | Candidata | Estado |",
        "|---|---|---|---|---|",
    ])
    for name in ("W4-OfficeServer", "W4-OfficeDesktop"):
        repo = f"W4MEX/{name}"
        ref, tree = tip(repo)
        config = content(repo, ref, ".gitmodules")
        required = {"web-apps"}
        if name == "W4-OfficeDesktop":
            required.add("desktop-apps")
        for item in api(f"repos/{repo}/git/trees/{tree}")["tree"]:
            if item["mode"] != "160000":
                continue
            path, old = item["path"], item["sha"]
            upstream = W4_PINS.get(path)
            if upstream is None and path in UPSTREAM_PINS:
                upstream = f"Euro-Office/{path}"
            if upstream is None or module_url(config, path) != f"https://github.com/{upstream}.git":
                raise ValueError(f"{name}/{path}: origen inesperado; requiere revisión")
            required.discard(path)
            new, _ = tip(upstream)
            result = comparison(upstream, old, new)
            count = result["ahead_by"]
            states = {
                "identical": "Actual",
                "ahead": f"{count} {'commit' if count == 1 else 'commits'} por revisar",
                "behind": "La candidata retrocede",
                "diverged": "Historial divergente",
            }
            lines.append(
                f"| {name} | {path} | {link(upstream, old)} | {link(upstream, new)} "
                f"| {states[result['status']]} |"
            )
        if required:
            raise ValueError(f"{name}: faltan referencias de {', '.join(sorted(required))}")

    web = W4_PINS["web-apps"]
    config = json.loads(content(web, tip(web)[0], "theme/w4-office/meta/config.json"))
    if (config.get("app_title"), config.get("publisher_name")) != ("W4 Office", "W4"):
        raise ValueError("La identidad del tema w4-office cambió; requiere revisión")
    for component, (approved, paths) in APPROVED_ARTWORK.items():
        repo = W4_PINS[component]
        for path in paths:
            if content(repo, tip(repo)[0], path) != content(repo, approved, path):
                raise ValueError(f"{repo}/{path}: el recurso W4 cambió; requiere revisión")
    lines.extend([
        "", "## Marca W4", "",
        "El origen de los submódulos y la identidad del tema son correctos.",
        "Los logotipos claro y oscuro y el icono de Windows coinciden con las revisiones aprobadas.",
        "Falta comprobar cada artefacto compilado.",
        "Revisa cambios de core y SDK juntos cuando compartan una dependencia.",
        "Para Server, prepara la actualización de WebApps con el flujo dedicado.",
    ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    try:
        Path(sys.argv[1]).write_text(audit(), encoding="utf-8")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"No se pudo completar la auditoría: {error}")
