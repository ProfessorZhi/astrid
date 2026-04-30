from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256


@dataclass(slots=True)
class SkillSummary:
    name: str
    description: str
    path: str
    source: str


@dataclass(slots=True)
class LoadedSkill(SkillSummary):
    content: str


def extract_description(markdown: str) -> str:
    normalized = markdown.lstrip("\ufeff").replace("\r\n", "\n")
    if normalized.startswith("---\n"):
        closing = normalized.find("\n---\n", 4)
        if closing != -1:
            normalized = normalized[closing + 5 :]
    paragraphs = [block.strip() for block in normalized.split("\n\n") if block.strip()]
    for block in paragraphs:
        if block.startswith("#"):
            continue
        for line in [part.strip() for part in block.split("\n")]:
            if line and not line.startswith("#"):
                return line.replace("`", "")
    return "No description provided."


def _home_dir() -> Path:
    return Path.home()


def _user_skills_root() -> Path:
    return _home_dir() / ".astrid" / "skills"


def _default_backing_skills_root() -> Path:
    if sys.platform == "win32":
        return Path("F:/funnyskills/astrid-skills")
    return _user_skills_root()


def _external_skills_root() -> Path:
    configured = os.environ.get("ASTRID_SKILLS_ROOT")
    if configured:
        return Path(configured)
    return _default_backing_skills_root()


def _workspace_id(cwd: str | Path) -> str:
    try:
        resolved = str(Path(cwd).resolve())
    except OSError:
        resolved = str(Path(cwd))
    key = resolved.lower() if sys.platform == "win32" else resolved
    return sha256(key.encode("utf-8")).hexdigest()[:16]


def _project_state_skills_root(cwd: str | Path) -> Path:
    return _home_dir() / ".astrid" / "projects" / _workspace_id(cwd) / "skills"


def _is_directory_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def _link_points_to(path: Path, target: Path) -> bool:
    try:
        return path.resolve() == target.resolve()
    except OSError:
        return False


def _copy_missing_skill_dirs(source_root: Path, target_root: Path) -> None:
    if not source_root.exists():
        return
    target_root.mkdir(parents=True, exist_ok=True)
    for entry in source_root.iterdir():
        if not entry.is_dir():
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.exists():
            continue
        target_dir = target_root / entry.name
        if target_dir.exists():
            continue
        shutil.copytree(entry, target_dir)


def _backup_path(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.backup-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.backup-{stamp}-{counter}")
        counter += 1
    return candidate


def _ensure_directory_link(link_path: Path, target_path: Path) -> None:
    if link_path.exists() or link_path.is_symlink():
        if _is_directory_symlink(link_path):
            if _link_points_to(link_path, target_path):
                return
            link_path.unlink()
        else:
            _copy_missing_skill_dirs(link_path, target_path)
            link_path.rename(_backup_path(link_path))

    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        link_path.symlink_to(target_path, target_is_directory=True)
    except OSError as exc:
        raise RuntimeError(
            f"Failed to link Astrid skills entry {link_path} -> {target_path}. "
            "Create the directory link manually or set ASTRID_SKILLS_ROOT."
        ) from exc


def _ensure_user_skills_entry(backing_root: Path) -> None:
    user_root = _user_skills_root()
    if user_root == backing_root:
        return
    _ensure_directory_link(user_root, backing_root)


def _migrate_legacy_project_skills(cwd: str | Path, backing_root: Path) -> None:
    legacy_root = Path(cwd) / ".astrid" / "skills"
    if not legacy_root.exists() or _is_directory_symlink(legacy_root):
        return
    _copy_missing_skill_dirs(legacy_root, backing_root)
    legacy_root.rename(_backup_path(legacy_root))
    legacy_parent = legacy_root.parent
    try:
        if legacy_parent.exists() and not any(legacy_parent.iterdir()):
            legacy_parent.rmdir()
    except OSError:
        pass


_DEFAULT_SKILL_FILES: dict[str, str] = {
    "skill-creator": """# Skill Creator

Create a new Astrid skill folder with a `SKILL.md`, a short description, usage notes, and any helper files the workflow needs.
Use this when you want Astrid to gain a reusable local workflow.
""",
    "skill-installer": """# Skill Installer

Install a skill into Astrid's external skill library and verify it appears in `/skills`.
Use this when you want to add or update a reusable Astrid workflow from a local folder.
""",
    "pet-image-importer": """# Pet Image Importer

Turn a local image file path or image URL into an Astrid preset pet.

Workflow:
1. Run `/pet import <path-or-url>` to generate the sprite.
2. If needed, switch style with `/pet mode ascii` or `/pet mode ansi`.
3. Save it with `/pet save <name>`.
4. Later restore it with `/pet use <name>`.

Use this when the user gives you an image path or image URL and wants it converted into a reusable terminal pet.
""",
}


def _ensure_external_skill_library() -> Path:
    root = _external_skills_root()
    root.mkdir(parents=True, exist_ok=True)
    _ensure_user_skills_entry(root)
    for name, content in _DEFAULT_SKILL_FILES.items():
        skill_dir = root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            skill_file.write_text(content, encoding="utf-8")
    return root


def _skill_roots(cwd: str | Path) -> list[tuple[Path, str]]:
    external_root = _ensure_external_skill_library()
    _migrate_legacy_project_skills(cwd, external_root)
    project_root = _project_state_skills_root(cwd)
    roots: list[tuple[Path, str]] = [(project_root, "project")]
    roots.append((external_root, "user"))
    return roots


def _list_skill_dirs(root: Path, source: str) -> list[LoadedSkill]:
    if not root.exists():
        return []
    results: list[LoadedSkill] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        skill_path = entry / "SKILL.md"
        if not skill_path.exists():
            continue
        content = skill_path.read_text(encoding="utf-8-sig")
        results.append(
            LoadedSkill(
                name=entry.name,
                description=extract_description(content),
                path=str(skill_path),
                source=source,
                content=content,
            )
        )
    return results


def discover_skills(cwd: str | Path) -> list[SkillSummary]:
    by_name: dict[str, LoadedSkill] = {}
    for root, source in _skill_roots(cwd):
        for skill in _list_skill_dirs(root, source):
            by_name.setdefault(skill.name, skill)
    return [
        SkillSummary(
            name=skill.name,
            description=skill.description,
            path=skill.path,
            source=skill.source,
        )
        for skill in by_name.values()
    ]


def load_skill(cwd: str | Path, name: str) -> LoadedSkill | None:
    normalized_name = name.strip()
    if not normalized_name:
        return None
    for root, source in _skill_roots(cwd):
        skill_path = root / normalized_name / "SKILL.md"
        if skill_path.exists():
            content = skill_path.read_text(encoding="utf-8")
            return LoadedSkill(
                name=normalized_name,
                description=extract_description(content),
                path=str(skill_path),
                source=source,
                content=content,
            )
    return None


def _managed_skill_root(scope: str, cwd: str | Path) -> Path:
    if scope == "project":
        return _project_state_skills_root(cwd)
    return _ensure_external_skill_library()


def install_skill(cwd: str | Path, source_path: str, name: str | None = None, scope: str = "user") -> dict[str, str]:
    source = Path(source_path)
    if not source.is_absolute():
        source = Path(cwd) / source
    source_dir = source if source.is_dir() else source.parent
    if source.is_dir():
        skill_file = source / "SKILL.md"
        inferred_name = source.name
    else:
        skill_file = source if source.name == "SKILL.md" else source / "SKILL.md"
        inferred_name = skill_file.parent.name
    if not skill_file.exists():
        raise RuntimeError(f"No SKILL.md found in {source}")

    skill_name = (name or inferred_name).strip()
    if not skill_name:
        raise RuntimeError("Skill name cannot be empty.")

    target_dir = _managed_skill_root(scope, cwd) / skill_name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    return {"name": skill_name, "targetPath": str(target_dir / "SKILL.md")}


def remove_managed_skill(cwd: str | Path, name: str, scope: str = "user") -> dict[str, object]:
    target_path = _managed_skill_root(scope, cwd) / name
    if not target_path.exists():
        return {"removed": False, "targetPath": str(target_path)}
    shutil.rmtree(target_path)
    return {"removed": True, "targetPath": str(target_path)}
