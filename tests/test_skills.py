from pathlib import Path

from astrid.integrations.skills import (
    _external_skills_root,
    _user_skills_root,
    discover_skills,
    extract_description,
    install_skill,
    load_skill,
)


def test_discover_skills_ignores_project_root_by_default(tmp_path: Path, monkeypatch) -> None:
    project_skill = tmp_path / ".astrid" / "skills" / "demo" / "SKILL.md"
    project_skill.parent.mkdir(parents=True)
    project_skill.write_text("# Demo\n\nProject description\n", encoding="utf-8")

    user_home = tmp_path / "home"
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(tmp_path / "astrid-skills"))
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("USERPROFILE", str(user_home))
    user_skill = user_home / ".astrid" / "skills" / "demo" / "SKILL.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("# Demo\n\nUser description\n", encoding="utf-8")

    skills = discover_skills(tmp_path)
    demo = next(skill for skill in skills if skill.name == "demo")
    assert demo.description == "User description"
    assert demo.source == "user"
    loaded = load_skill(tmp_path, "demo")
    assert loaded is not None
    assert "User description" in loaded.content


def test_discover_skills_uses_external_root_and_seeds_default_skills(tmp_path: Path, monkeypatch) -> None:
    external_root = tmp_path / "astrid-skills"
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(external_root))

    custom_skill = external_root / "demo" / "SKILL.md"
    custom_skill.parent.mkdir(parents=True)
    custom_skill.write_text("# Demo\n\nExternal description\n", encoding="utf-8")

    skills = discover_skills(tmp_path)
    names = {skill.name for skill in skills}

    assert "demo" in names
    assert "skill-creator" in names
    assert "skill-installer" in names
    assert "pet-image-importer" in names
    assert (external_root / "skill-creator" / "SKILL.md").exists()
    assert (external_root / "skill-installer" / "SKILL.md").exists()


def test_install_skill_writes_to_external_user_root_by_default(tmp_path: Path, monkeypatch) -> None:
    external_root = tmp_path / "astrid-skills"
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(external_root))

    source = tmp_path / "source-skill" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Source\n\nSource description\n", encoding="utf-8")

    result = install_skill(tmp_path, str(source.parent))

    assert Path(result["targetPath"]) == external_root / "source-skill" / "SKILL.md"
    assert Path(result["targetPath"]).read_text(encoding="utf-8").startswith("# Source")


def test_install_skill_copies_helper_files_with_skill(tmp_path: Path, monkeypatch) -> None:
    external_root = tmp_path / "astrid-skills"
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(external_root))

    source_dir = tmp_path / "source-skill"
    source_dir.mkdir(parents=True)
    (source_dir / "SKILL.md").write_text("# Source\n\nSource description\n", encoding="utf-8")
    (source_dir / "script.py").write_text("print('helper')\n", encoding="utf-8")
    (source_dir / "assets").mkdir()
    (source_dir / "assets" / "prompt.txt").write_text("helper prompt\n", encoding="utf-8")

    install_skill(tmp_path, str(source_dir))

    assert (external_root / "source-skill" / "SKILL.md").exists()
    assert (external_root / "source-skill" / "script.py").read_text(encoding="utf-8") == "print('helper')\n"
    assert (external_root / "source-skill" / "assets" / "prompt.txt").read_text(encoding="utf-8") == "helper prompt\n"


def test_external_skill_root_defaults_to_user_astrid_skills(tmp_path: Path, monkeypatch) -> None:
    user_home = tmp_path / "home"
    monkeypatch.delenv("ASTRID_SKILLS_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("USERPROFILE", str(user_home))
    monkeypatch.setattr("astrid.integrations.skills.sys.platform", "win32")

    assert _user_skills_root() == user_home / ".astrid" / "skills"
    assert _external_skills_root() == Path("F:/funnyskills/astrid-skills")


def test_existing_user_skills_directory_is_migrated_to_backing_root(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    backing = tmp_path / "backing"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(backing))

    old_skill = home / ".astrid" / "skills" / "legacy" / "SKILL.md"
    old_skill.parent.mkdir(parents=True)
    old_skill.write_text("# Legacy\n\nLegacy description\n", encoding="utf-8")

    discovered = discover_skills(tmp_path)

    assert (backing / "legacy" / "SKILL.md").read_text(encoding="utf-8").startswith("# Legacy")
    assert any(skill.name == "legacy" for skill in discovered)
    assert (home / ".astrid" / "skills").is_symlink()
    assert list((home / ".astrid").glob("skills.backup-*"))


def test_migration_keeps_existing_backing_skill_on_conflict(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    backing = tmp_path / "backing"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(backing))

    old_skill = home / ".astrid" / "skills" / "demo" / "SKILL.md"
    old_skill.parent.mkdir(parents=True)
    old_skill.write_text("# Demo\n\nOld C drive description\n", encoding="utf-8")
    backing_skill = backing / "demo" / "SKILL.md"
    backing_skill.parent.mkdir(parents=True)
    backing_skill.write_text("# Demo\n\nF drive description\n", encoding="utf-8")

    discover_skills(tmp_path)

    assert backing_skill.read_text(encoding="utf-8") == "# Demo\n\nF drive description\n"


def test_install_project_skill_writes_to_user_project_state(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    backing = tmp_path / "backing"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(backing))

    source = tmp_path / "source-skill"
    source.mkdir()
    (source / "SKILL.md").write_text("# Source\n\nSource description\n", encoding="utf-8")

    result = install_skill(tmp_path, str(source), scope="project")
    target_path = Path(result["targetPath"])

    assert target_path.is_relative_to(home / ".astrid" / "projects")
    assert target_path.name == "SKILL.md"
    assert not (tmp_path / ".astrid").exists()


def test_install_user_skill_does_not_create_project_astrid_directory(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    backing = tmp_path / "backing"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(backing))

    source = tmp_path / "source-skill"
    source.mkdir()
    (source / "SKILL.md").write_text("# Source\n\nSource description\n", encoding="utf-8")

    install_skill(tmp_path, str(source))

    assert (backing / "source-skill" / "SKILL.md").exists()
    assert not (tmp_path / ".astrid").exists()


def test_legacy_project_skill_directory_is_migrated_to_backing_root(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    backing = tmp_path / "backing"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(backing))

    legacy_skill = tmp_path / ".astrid" / "skills" / "project-only" / "SKILL.md"
    legacy_skill.parent.mkdir(parents=True)
    legacy_skill.write_text("# Project Only\n\nProject-only description\n", encoding="utf-8")

    skills = discover_skills(tmp_path)

    assert "project-only" in {skill.name for skill in skills}
    assert (backing / "project-only" / "SKILL.md").exists()
    assert not (tmp_path / ".astrid" / "skills").exists()
    assert list((tmp_path / ".astrid").glob("skills.backup-*"))


def test_discover_skills_ignores_claude_skill_folders(tmp_path: Path, monkeypatch) -> None:
    user_home = tmp_path / "home"
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(tmp_path / "astrid-skills"))
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("USERPROFILE", str(user_home))

    project_claude_skill = tmp_path / ".claude" / "skills" / "leak" / "SKILL.md"
    project_claude_skill.parent.mkdir(parents=True)
    project_claude_skill.write_text("# Leak\n\nProject Claude skill\n", encoding="utf-8")
    user_claude_skill = user_home / ".claude" / "skills" / "leak-user" / "SKILL.md"
    user_claude_skill.parent.mkdir(parents=True)
    user_claude_skill.write_text("# Leak User\n\nUser Claude skill\n", encoding="utf-8")

    names = {skill.name for skill in discover_skills(tmp_path)}

    assert "leak" not in names
    assert "leak-user" not in names


def test_extract_description_skips_yaml_frontmatter_and_bom() -> None:
    markdown = "\ufeff---\nname: demo\ndescription: sample\n---\n# Demo\n\nReal description\n"

    assert extract_description(markdown) == "Real description"
