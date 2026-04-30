from __future__ import annotations

from .buddy import _render_species_lines, normalize_buddy_species, _rarity_color
from .buddy_state import BuddyProfile, BuddyRuntimeState
from .theme import theme


def _species_title(species: str) -> str:
    return normalize_buddy_species(species).capitalize()


def render_welcome_hero_profile_block(
    profile: BuddyProfile,
    runtime: BuddyRuntimeState,
    animation_tick: int,
) -> str:
    """Render the welcome pet as one of the built-in 18 ASCII pets.

    The welcome screen should match the standard pet gallery, not the separate
    mascot experiment. Keep it simple: built-in sprite + species label.
    """
    species = normalize_buddy_species(profile.bones.species)
    t = theme()
    color = _rarity_color(profile)
    lines = [f"{color}{line}{t.reset}" for line in _render_species_lines(species, animation_tick, eye="o", hat="none")]
    while lines and not lines[0].strip():
        lines.pop(0)
    lines.append("")
    lines.append(f"{t.progress}{_species_title(species)}{t.reset}")
    return "\n".join(lines)
