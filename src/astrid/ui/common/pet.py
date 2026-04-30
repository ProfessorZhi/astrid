from __future__ import annotations

import random

from astrid.runtime.config import load_pet_settings
from astrid.tui.buddy import BUDDY_SPECIES
from astrid.tui.buddy_state import BuddyRuntimeState, build_buddy_profile
from astrid.tui.welcome_hero import render_welcome_hero_profile_block


def pick_startup_pet(*, seed: str, animation_tick: int = 0) -> str:
    """Render the shared startup pet used by shell, inline, and full UIs."""
    settings = load_pet_settings()
    species = settings.get("companionSpecies")
    if not species or species not in BUDDY_SPECIES:
        species = random.choice(BUDDY_SPECIES)
    profile = build_buddy_profile(seed, species_override=species)
    return render_welcome_hero_profile_block(profile, BuddyRuntimeState(), animation_tick)
