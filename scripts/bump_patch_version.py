from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Não encontrei o texto esperado em {path}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    current = VERSION_FILE.read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", current)
    if not match:
        raise SystemExit(f"VERSION inválida: {current!r}")

    major, minor, patch = map(int, match.groups())
    new_version = f"{major}.{minor}.{patch + 1}"

    VERSION_FILE.write_text(new_version + "\n", encoding="utf-8")

    replace_once(
        ROOT / "pyproject.toml",
        f'version = "{current}"',
        f'version = "{new_version}"',
    )
    replace_once(
        ROOT / "qbx" / "__init__.py",
        f'__version__ = "{current}"',
        f'__version__ = "{new_version}"',
    )

    readme = ROOT / "README.md"
    readme_text = readme.read_text(encoding="utf-8")
    readme.write_text(readme_text.replace(current, new_version), encoding="utf-8")

    changelog = ROOT / "CHANGELOG.md"
    changelog_text = changelog.read_text(encoding="utf-8")
    pending = "## Próxima versão — Pesquisa autônoma"
    if pending in changelog_text:
        changelog_text = changelog_text.replace(
            pending,
            f"## {new_version} — Pesquisa autônoma validada",
            1,
        )
    else:
        marker = "# Changelog\n"
        entry = (
            f"\n## {new_version} — Pesquisa autônoma validada\n\n"
            "- Versão criada automaticamente depois que a rodada passou por "
            "testes, benchmarks e validação do instalador.\n"
        )
        if marker not in changelog_text:
            raise SystemExit("CHANGELOG.md não tem o cabeçalho esperado")
        changelog_text = changelog_text.replace(marker, marker + entry, 1)
    changelog.write_text(changelog_text, encoding="utf-8")

    print(new_version)


if __name__ == "__main__":
    main()
