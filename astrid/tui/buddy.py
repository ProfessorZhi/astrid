from __future__ import annotations

from typing import Final

from .buddy_state import BuddyProfile, BuddyRuntimeState
from .theme import theme

BUDDY_SPECIES: Final[tuple[str, ...]] = (
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

# Claude Code-inspired sprite bodies:
# - fixed, curated per-species frames
# - line 0 is the hat slot
# - {E} is replaced with the current eye glyph
_BODIES: Final[dict[str, tuple[tuple[str, ...], ...]]] = {
    "duck": (
        ("            ", "    __      ", "  <({E} )___ ", "   (  ._>   ", "    `--'    "),
        ("            ", "    __      ", "  <({E} )___ ", "   (  ._>   ", "    `--'~   "),
        ("            ", "    __      ", "  <({E} )___ ", "   (  .__>  ", "    `--'    "),
    ),
    "goose": (
        ("            ", "     ({E}>    ", "     ||     ", "   _(__)_   ", "    ^^^^    "),
        ("            ", "    ({E}>     ", "     ||     ", "   _(__)_   ", "    ^^^^    "),
        ("            ", "     ({E}>>   ", "     ||     ", "   _(__)_   ", "    ^^^^    "),
    ),
    "blob": (
        ("            ", "   .----.   ", "  ( {E}  {E} )  ", "  (      )  ", "   `----'   "),
        ("            ", "  .------.  ", " (  {E}  {E}  ) ", " (        ) ", "  `------'  "),
        ("            ", "    .--.    ", "   ({E}  {E})   ", "   (    )   ", "    `--'    "),
    ),
    "cat": (
        ("            ", "   /\\_/\\\\    ", "  ( {E}   {E})  ", "  (  ^  )   ", '  (")_(")   '),
        ("            ", "   /\\_/\\\\    ", "  ( {E}   {E})  ", "  (  ^  )   ", '  (")_(")~  '),
        ("            ", "   /\\-/\\\\    ", "  ( {E}   {E})  ", "  (  ^  )   ", '  (")_(")   '),
    ),
    "dragon": (
        ("            ", "  /^\\\\  /^\\\\  ", " <  {E}  {E}  > ", " (   ~~   ) ", "  `-vvvv-'  "),
        ("            ", "  /^\\\\  /^\\\\  ", " <  {E}  {E}  > ", " (        ) ", "  `-vvvv-'  "),
        ("   ~    ~   ", "  /^\\\\  /^\\\\  ", " <  {E}  {E}  > ", " (   ~~   ) ", "  `-vvvv-'  "),
    ),
    "octopus": (
        ("            ", "   .----.   ", "  ( {E}  {E} )  ", "  (______)  ", "  /\\\\/\\\\/\\\\/\\\\  "),
        ("            ", "   .----.   ", "  ( {E}  {E} )  ", "  (______)  ", "  \\\\/\\\\/\\\\/\\\\/  "),
        ("     o      ", "   .----.   ", "  ( {E}  {E} )  ", "  (______)  ", "  /\\\\/\\\\/\\\\/\\\\  "),
    ),
    "owl": (
        ("            ", "   /\\\\  /\\\\   ", "  (({E})({E}))  ", "  (  ><  )  ", "   `----'   "),
        ("            ", "   /\\\\  /\\\\   ", "  (({E})({E}))  ", "  (  ><  )  ", "   .----.   "),
        ("            ", "   /\\\\  /\\\\   ", "  (({E})(-))  ", "  (  ><  )  ", "   `----'   "),
    ),
    "penguin": (
        ("            ", "  .---.     ", "  ({E}>{E})     ", " /(   )\\\\    ", "  `---'     "),
        ("            ", "  .---.     ", "  ({E}>{E})     ", " |(   )|    ", "  `---'     "),
        ("  .---.     ", "  ({E}>{E})     ", " /(   )\\\\    ", "  `---'     ", "   ~ ~      "),
    ),
    "turtle": (
        ("            ", "   _,--._   ", "  ( {E}  {E} )  ", " /[______]\\\\ ", "  ``    ``  "),
        ("            ", "   _,--._   ", "  ( {E}  {E} )  ", " /[______]\\\\ ", "   ``  ``   "),
        ("            ", "   _,--._   ", "  ( {E}  {E} )  ", " /[======]\\\\ ", "  ``    ``  "),
    ),
    "snail": (
        ("            ", " {E}    .--.  ", "  \\\\  ( @ )  ", "   \\\\_`--'   ", "  ~~~~~~~   "),
        ("            ", "  {E}   .--.  ", "  |  ( @ )  ", "   \\\\_`--'   ", "  ~~~~~~~   "),
        ("            ", " {E}    .--.  ", "  \\\\  ( @  ) ", "   \\\\_`--'   ", "   ~~~~~~   "),
    ),
    "ghost": (
        ("            ", "   .----.   ", "  / {E}  {E} \\\\  ", "  |      |  ", "  ~`~``~`~  "),
        ("            ", "   .----.   ", "  / {E}  {E} \\\\  ", "  |      |  ", "  `~`~~`~`  "),
        ("    ~  ~    ", "   .----.   ", "  / {E}  {E} \\\\  ", "  |      |  ", "  ~~`~~`~~  "),
    ),
    "axolotl": (
        ("            ", "}~(______)~{", "}~({E} .. {E})~{", "  ( .--. )  ", "  (_/  \\\\_)  "),
        ("            ", "~}(______){~", "~}({E} .. {E}){~", "  ( .--. )  ", "  (_/  \\\\_)  "),
        ("            ", "}~(______)~{", "}~({E} .. {E})~{", "  (  --  )  ", "  ~_/  \\\\_~  "),
    ),
    "capybara": (
        ("            ", "  n______n  ", " ( {E}    {E} ) ", " (   oo   ) ", "  `------'  "),
        ("            ", "  n______n  ", " ( {E}    {E} ) ", " (   Oo   ) ", "  `------'  "),
        ("    ~  ~    ", "  u______n  ", " ( {E}    {E} ) ", " (   oo   ) ", "  `------'  "),
    ),
    "cactus": (
        ("            ", " n  ____  n ", " | |{E}  {E}| | ", " |_|    |_| ", "   |    |   "),
        ("            ", "    ____    ", " n |{E}  {E}| n ", " |_|    |_| ", "   |    |   "),
        (" n        n ", " |  ____  | ", " | |{E}  {E}| | ", " |_|    |_| ", "   |    |   "),
    ),
    "robot": (
        ("            ", "   .[||].   ", "  [ {E}  {E} ]  ", "  [ ==== ]  ", "  `------'  "),
        ("            ", "   .[||].   ", "  [ {E}  {E} ]  ", "  [ -==- ]  ", "  `------'  "),
        ("     *      ", "   .[||].   ", "  [ {E}  {E} ]  ", "  [ ==== ]  ", "  `------'  "),
    ),
    "rabbit": (
        ("            ", "   (\\\\__/)   ", "  ( {E}  {E} )  ", " =(  ..  )= ", '  (")__(")  '),
        ("            ", "   (|__/)   ", "  ( {E}  {E} )  ", " =(  ..  )= ", '  (")__(")  '),
        ("            ", "   (\\\\__/)   ", "  ( {E}  {E} )  ", " =( .  . )= ", '  (")__(")  '),
    ),
    "mushroom": (
        ("            ", " .-o-OO-o-. ", "(__________)", "   |{E}  {E}|   ", "   |____|   "),
        ("            ", " .-O-oo-O-. ", "(__________)", "   |{E}  {E}|   ", "   |____|   "),
        ("   . o  .   ", " .-o-OO-o-. ", "(__________)", "   |{E}  {E}|   ", "   |____|   "),
    ),
    "chonk": (
        ("            ", "  /\\\\    /\\\\  ", " ( {E}    {E} ) ", " (   ..   ) ", "  `------'  "),
        ("            ", "  /\\\\    /|  ", " ( {E}    {E} ) ", " (   ..   ) ", "  `------'  "),
        ("            ", "  /\\\\    /\\\\  ", " ( {E}    {E} ) ", " (   ..   ) ", "  `------'~ "),
    ),
}

_HAT_LINES: Final[dict[str, str]] = {
    "none": "",
    "crown": "   \\^^^/    ",
    "tophat": "   [___]    ",
    "beanie": "   (___)    ",
    "halo": "   (   )    ",
}

_HEART_FRAMES: Final[tuple[tuple[str, ...], ...]] = (
    ("   ♥  ♥", "     ♥"),
    ("  ♥ ♥ ♥", "    ♥ "),
    ("    ♥♥", "  ♥  ♥"),
)

_RARITY_TITLES: Final[dict[str, tuple[str, str]]] = {
    "common": ("Field Buddy", "*"),
    "uncommon": ("Trusted Buddy", "**"),
    "rare": ("Star Buddy", "***"),
    "epic": ("Mythic Buddy", "****"),
    "legendary": ("Cosmic Buddy", "*****"),
}

_RARITY_COLORS: Final[dict[str, str]] = {
    "common": "\x1b[38;5;180m",
    "uncommon": "\x1b[38;5;151m",
    "rare": "\x1b[38;5;117m",
    "epic": "\x1b[38;5;183m",
    "legendary": "\x1b[38;5;221m",
}


def normalize_buddy_species(species: str | None) -> str:
    candidate = (species or "").strip().lower()
    return candidate if candidate in BUDDY_SPECIES else BUDDY_SPECIES[0]


def cycle_buddy_species(current: str | None, step: int = 1) -> str:
    species = normalize_buddy_species(current)
    index = BUDDY_SPECIES.index(species)
    return BUDDY_SPECIES[(index + step) % len(BUDDY_SPECIES)]


def _resolve_frame(species: str | None, animation_tick: int) -> tuple[str, ...]:
    pet = normalize_buddy_species(species)
    frames = _BODIES[pet]
    return frames[animation_tick % len(frames)]


def _replace_eye_slots(text: str, eye: str) -> str:
    return text.replace("{E}", eye)


def _render_species_lines(species: str | None, animation_tick: int, eye: str = "o", hat: str = "none") -> list[str]:
    frame = [_replace_eye_slots(line, eye) for line in _resolve_frame(species, animation_tick)]
    if hat != "none" and not frame[0].strip():
        frame[0] = _HAT_LINES.get(hat, "")
    if not frame[0].strip():
        all_blank = all(not species_frame[0].strip() for species_frame in _BODIES[normalize_buddy_species(species)])
        if all_blank:
            frame = frame[1:]
    return frame


def get_buddy_frame(species: str | None, animation_tick: int) -> tuple[str, ...]:
    return tuple(_resolve_frame(species, animation_tick))


def format_buddy_frame(species: str | None, animation_tick: int) -> tuple[str, ...]:
    pet = normalize_buddy_species(species)
    resolved = tuple(_render_species_lines(pet, animation_tick, eye="o"))
    return resolved + (f"{pet} buddy",)


def render_buddy_lines(species: str | None, animation_tick: int) -> tuple[str, ...]:
    return format_buddy_frame(species, animation_tick)


def render_buddy_block(species: str | None, animation_tick: int) -> str:
    return "\n".join(render_buddy_lines(species, animation_tick))


def _compose_sprite_lines(profile: BuddyProfile, animation_tick: int, *, hero: bool = False) -> list[str]:
    sprite = _render_species_lines(
        profile.bones.species,
        animation_tick,
        eye="o" if hero else profile.bones.eye,
        hat="none" if hero else profile.bones.hat,
    )
    if profile.bones.shiny and sprite and not hero:
        sprite[0] = f"{sprite[0]} *"
    return sprite


def _render_bubble_lines(text: str) -> tuple[str, ...]:
    bubble_text = text[:40]
    border = "-" * (len(bubble_text) + 2)
    return (f" .{border}.", f" | {bubble_text} |", f" '{border}'")


def _rarity_color(profile: BuddyProfile) -> str:
    return _RARITY_COLORS.get(profile.bones.rarity, _RARITY_COLORS["common"])


def _render_rarity_line(profile: BuddyProfile) -> str:
    title, stars = _RARITY_TITLES.get(profile.bones.rarity, ("Buddy", "*"))
    color = _rarity_color(profile)
    t = theme()
    return f"{color}* {profile.soul.name} - {title} - {stars}{t.reset}"


def _hero_sprite_lines(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines = lines[1:]
    content_lines = [line for line in lines if line.strip()]
    if content_lines:
        common_indent = min(len(line) - len(line.lstrip(" ")) for line in content_lines)
        if common_indent > 0:
            lines = [line[common_indent:] if line.strip() else "" for line in lines]

    hero: list[str] = []
    for index, line in enumerate(lines):
        padded = f"  {line}"
        hero.append(padded)
        if index != 0 or not line.strip():
            hero.append(padded)
    return hero


def render_buddy_profile_lines(
    profile: BuddyProfile,
    runtime: BuddyRuntimeState,
    animation_tick: int,
    *,
    hero: bool = False,
) -> tuple[str, ...]:
    lines: list[str] = []
    color = _rarity_color(profile)
    t = theme()
    if runtime.is_petting():
        lines.extend(f"{color}{line}{t.reset}" for line in _HEART_FRAMES[animation_tick % len(_HEART_FRAMES)])
    if runtime.is_speaking() and runtime.reaction_text:
        lines.extend(f"{color}{line}{t.reset}" for line in _render_bubble_lines(runtime.reaction_text))
    sprite_lines = _compose_sprite_lines(profile, animation_tick, hero=hero)
    if hero:
        lines.append("")
        sprite_lines = _hero_sprite_lines(sprite_lines)
    lines.extend(f"{color}{line}{t.reset}" for line in sprite_lines)
    lines.append("")
    lines.append(f"{color}{profile.bones.species} buddy{t.reset}")
    if hero:
        tag = " shiny" if profile.bones.shiny else ""
        _, stars = _RARITY_TITLES.get(profile.bones.rarity, ("Buddy", "*"))
        lines.append(f"{t.subtle}{profile.soul.name}{tag} / {stars}{t.reset}")
    else:
        lines.append(_render_rarity_line(profile))
        shiny = " shiny" if profile.bones.shiny else ""
        lines.append(
            f"{t.subtle}{profile.soul.persona} - eye {profile.bones.eye} - hat {profile.bones.hat}{shiny}{t.reset}"
        )
    return tuple(lines)


def render_buddy_profile_block(
    profile: BuddyProfile,
    runtime: BuddyRuntimeState,
    animation_tick: int,
    *,
    hero: bool = False,
) -> str:
    return "\n".join(render_buddy_profile_lines(profile, runtime, animation_tick, hero=hero))


def render_buddy_overlay(profile: BuddyProfile, runtime: BuddyRuntimeState) -> str:
    """Compact active-view buddy reaction that reads like a floating hint."""
    if not runtime.is_speaking() or not runtime.reaction_text:
        return ""
    color = _rarity_color(profile)
    title, _ = _RARITY_TITLES.get(profile.bones.rarity, ("Buddy", "*"))
    t = theme()
    body = f"* {profile.soul.name} [{title}] says: {runtime.reaction_text}"
    border = "-" * max(12, len(body))
    return "\n".join(
        (
            f"{color}+{border}+{t.reset}",
            f"{color}|{t.reset} {body} {color}|{t.reset}",
            f"{color}+{border}+{t.reset}",
        )
    )
