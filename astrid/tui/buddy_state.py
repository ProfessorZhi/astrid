from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time

_RARITIES = ("common", "uncommon", "rare", "epic", "legendary")
_EYES = ("o", "O", ".", "^", "-", "*")
_HATS = ("none", "crown", "tophat", "beanie", "halo")
_SPECIES = (
    "duck",
    "goose",
    "blob",
    "cat",
    "dragon",
    "octopus",
    "owl",
    "penguin",
    "turtle",
    "snail",
    "ghost",
    "axolotl",
    "capybara",
    "cactus",
    "robot",
    "rabbit",
    "mushroom",
    "chonk",
)
_NAMES = (
    "Clove",
    "Mallow",
    "Sable",
    "Pip",
    "Rune",
    "Cinder",
    "Tango",
    "Drift",
)
_PERSONAS = (
    "calm reviewer",
    "curious scout",
    "cheeky debugger",
    "steady builder",
)


@dataclass(frozen=True, slots=True)
class BuddyBones:
    species: str
    rarity: str
    eye: str
    hat: str
    shiny: bool


@dataclass(frozen=True, slots=True)
class BuddySoul:
    name: str
    persona: str
    hatched_at: int


@dataclass(slots=True)
class BuddyProfile:
    bones: BuddyBones
    soul: BuddySoul


@dataclass(slots=True)
class BuddyRuntimeState:
    reaction_text: str | None = None
    reaction_until: float = 0.0
    pet_until: float = 0.0
    summoned_until: float = 0.0

    def is_speaking(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        return bool(self.reaction_text) and current < self.reaction_until

    def is_petting(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        return current < self.pet_until

    def is_summoned(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        return current < self.summoned_until


def _pick(values: tuple[str, ...], digest: bytes, index: int) -> str:
    return values[digest[index] % len(values)]


def derive_buddy_bones(seed: str, species_override: str | None = None) -> BuddyBones:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    chosen_species = species_override if species_override in _SPECIES else _SPECIES[digest[0] % len(_SPECIES)]
    return BuddyBones(
        species=chosen_species,
        rarity=_pick(_RARITIES, digest, 1),
        eye=_pick(_EYES, digest, 2),
        hat=_pick(_HATS, digest, 3),
        shiny=(digest[4] % 20) == 0,
    )


def build_buddy_soul(seed: str) -> BuddySoul:
    digest = hashlib.sha256(f"soul:{seed}".encode("utf-8")).digest()
    hatched_at = int.from_bytes(digest[:4], "big")
    return BuddySoul(
        name=_pick(_NAMES, digest, 4),
        persona=_pick(_PERSONAS, digest, 5),
        hatched_at=hatched_at,
    )


def build_buddy_profile(seed: str, species_override: str | None = None) -> BuddyProfile:
    return BuddyProfile(
        bones=derive_buddy_bones(seed, species_override=species_override),
        soul=build_buddy_soul(seed),
    )
