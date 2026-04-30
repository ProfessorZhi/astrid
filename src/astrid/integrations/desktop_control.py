from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def _load_pyautogui():
    try:
        import pyautogui  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "PyAutoGUI is not installed. Install desktop dependencies first."
        ) from exc
    return pyautogui


def _load_pygetwindow():
    try:
        import pygetwindow  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "PyGetWindow is not installed. Install desktop dependencies first."
        ) from exc
    return pygetwindow


def focus_window(title_substring: str) -> dict[str, Any]:
    windows = _load_pygetwindow().getAllWindows()
    lowered = title_substring.lower()
    for window in windows:
        title = getattr(window, "title", "") or ""
        if lowered not in title.lower():
            continue
        if getattr(window, "isMinimized", False):
            window.restore()
        window.activate()
        return {
            "title": title,
            "rect": {
                "left": int(getattr(window, "left", 0)),
                "top": int(getattr(window, "top", 0)),
                "width": int(getattr(window, "width", 0)),
                "height": int(getattr(window, "height", 0)),
            },
        }
    raise RuntimeError(f"No window matching '{title_substring}' was found.")


def scroll_at(x: int, y: int, amount: int) -> None:
    pyautogui = _load_pyautogui()
    pyautogui.moveTo(x, y, duration=0.0)
    pyautogui.scroll(amount)


def click_at(x: int, y: int, *, button: str = "left", clicks: int = 1) -> None:
    pyautogui = _load_pyautogui()
    pyautogui.click(x=x, y=y, button=button, clicks=clicks)


def type_text(text: str, *, interval: float = 0.0) -> None:
    _load_pyautogui().write(text, interval=interval)


def press_key(key: str) -> None:
    _load_pyautogui().press(key)


def send_hotkey(*keys: str) -> None:
    _load_pyautogui().hotkey(*keys)


def take_screenshot(path: str | Path, *, region: tuple[int, int, int, int] | None = None) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image = _load_pyautogui().screenshot(region=region)
    image.save(str(target))
    return str(target)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Desktop control helpers for Astrid smoke tests.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    focus = subparsers.add_parser("focus-window")
    focus.add_argument("title")

    scroll = subparsers.add_parser("scroll")
    scroll.add_argument("x", type=int)
    scroll.add_argument("y", type=int)
    scroll.add_argument("amount", type=int)

    click = subparsers.add_parser("click")
    click.add_argument("x", type=int)
    click.add_argument("y", type=int)
    click.add_argument("--button", default="left")
    click.add_argument("--clicks", type=int, default=1)

    type_parser = subparsers.add_parser("type")
    type_parser.add_argument("text")
    type_parser.add_argument("--interval", type=float, default=0.0)

    press = subparsers.add_parser("press")
    press.add_argument("key")

    hotkey = subparsers.add_parser("hotkey")
    hotkey.add_argument("keys", nargs="+")

    screenshot = subparsers.add_parser("screenshot")
    screenshot.add_argument("path")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "focus-window":
        print(focus_window(args.title))
        return 0
    if args.command == "scroll":
        scroll_at(args.x, args.y, args.amount)
        return 0
    if args.command == "click":
        click_at(args.x, args.y, button=args.button, clicks=args.clicks)
        return 0
    if args.command == "type":
        type_text(args.text, interval=args.interval)
        return 0
    if args.command == "press":
        press_key(args.key)
        return 0
    if args.command == "hotkey":
        send_hotkey(*args.keys)
        return 0
    if args.command == "screenshot":
        print(take_screenshot(args.path))
        return 0
    raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
