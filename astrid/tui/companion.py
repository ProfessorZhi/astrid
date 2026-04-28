from __future__ import annotations

from astrid.tui.buddy import (
    BUDDY_SPECIES as COMPANION_SPECIES,
    cycle_buddy_species,
    normalize_buddy_species,
    render_buddy_block,
)


def normalize_companion_species(species: str | None) -> str:
    return normalize_buddy_species(species)


def cycle_companion_species(current: str | None, step: int = 1) -> str:
    return cycle_buddy_species(current, step)


def list_companion_species() -> tuple[str, ...]:
    return COMPANION_SPECIES


def render_companion_preview(species: str | None) -> str:
    pet = normalize_companion_species(species)
    lines = render_buddy_block(pet, 0).splitlines()
    if lines:
        lines[-1] = f"{pet} companion"
    return (
        f"{'\n'.join(lines)}\n"
        "Use /pet next, /pet switch <species>, or /pet hide."
    )
