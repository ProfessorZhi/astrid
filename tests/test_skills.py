from pathlib import Path

from astrid.skills import _external_skills_root, discover_skills, extract_description, install_skill, load_skill


def test_discover_skills_prefers_project_root(tmp_path: Path, monkeypatch) -> None:
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
    assert demo.description == "Project description"
    assert demo.source == "project"
    loaded = load_skill(tmp_path, "demo")
    assert loaded is not None
    assert loaded.content.startswith("# Demo")


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

    assert _external_skills_root() == user_home / ".astrid" / "skills"


def test_extract_description_skips_yaml_frontmatter_and_bom() -> None:
    markdown = "\ufeff---\nname: demo\ndescription: sample\n---\n# Demo\n\nReal description\n"

    assert extract_description(markdown) == "Real description"
