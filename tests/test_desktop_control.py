from __future__ import annotations

from pathlib import Path

import pytest

from astrid import desktop_control as desktop


class _FakeWindow:
    def __init__(self, title: str, *, left: int = 10, top: int = 20, width: int = 300, height: int = 200, minimized: bool = False) -> None:
        self.title = title
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.isMinimized = minimized
        self.restore_calls = 0
        self.activate_calls = 0

    def restore(self) -> None:
        self.restore_calls += 1
        self.isMinimized = False

    def activate(self) -> None:
        self.activate_calls += 1


class _FakeScreenshot:
    def __init__(self) -> None:
        self.saved_path: str | None = None

    def save(self, path: str) -> None:
        self.saved_path = path


class _FakePyAutoGui:
    def __init__(self) -> None:
        self.moves: list[tuple[int, int, float]] = []
        self.scrolls: list[int] = []
        self.clicks: list[tuple[int, int, str, int]] = []
        self.writes: list[tuple[str, float]] = []
        self.presses: list[str] = []
        self.hotkeys: list[tuple[str, ...]] = []
        self.screenshot_calls: list[tuple[tuple[int, int, int, int] | None, _FakeScreenshot]] = []

    def moveTo(self, x: int, y: int, duration: float = 0.0) -> None:
        self.moves.append((x, y, duration))

    def scroll(self, amount: int) -> None:
        self.scrolls.append(amount)

    def click(self, x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1) -> None:
        self.clicks.append((int(x or 0), int(y or 0), button, clicks))

    def write(self, text: str, interval: float = 0.0) -> None:
        self.writes.append((text, interval))

    def press(self, key: str) -> None:
        self.presses.append(key)

    def hotkey(self, *keys: str) -> None:
        self.hotkeys.append(tuple(keys))

    def screenshot(self, region: tuple[int, int, int, int] | None = None) -> _FakeScreenshot:
        shot = _FakeScreenshot()
        self.screenshot_calls.append((region, shot))
        return shot


def test_focus_window_activates_first_matching_title(monkeypatch) -> None:
    matching = _FakeWindow("Astrid Smoke")
    monkeypatch.setattr(
        desktop,
        "_load_pygetwindow",
        lambda: type("FakeGW", (), {"getAllWindows": lambda self=None: [_FakeWindow("Other"), matching]})(),
    )

    result = desktop.focus_window("Astrid")

    assert result["title"] == "Astrid Smoke"
    assert matching.activate_calls == 1
    assert result["rect"] == {"left": 10, "top": 20, "width": 300, "height": 200}


def test_focus_window_restores_minimized_window(monkeypatch) -> None:
    matching = _FakeWindow("Astrid Smoke", minimized=True)
    monkeypatch.setattr(
        desktop,
        "_load_pygetwindow",
        lambda: type("FakeGW", (), {"getAllWindows": lambda self=None: [matching]})(),
    )

    desktop.focus_window("Astrid")

    assert matching.restore_calls == 1
    assert matching.activate_calls == 1


def test_focus_window_raises_when_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        desktop,
        "_load_pygetwindow",
        lambda: type("FakeGW", (), {"getAllWindows": lambda self=None: []})(),
    )

    with pytest.raises(RuntimeError, match="No window matching"):
        desktop.focus_window("Astrid")


def test_scroll_at_moves_mouse_then_scrolls(monkeypatch) -> None:
    fake = _FakePyAutoGui()
    monkeypatch.setattr(desktop, "_load_pyautogui", lambda: fake)

    desktop.scroll_at(640, 480, -600)

    assert fake.moves == [(640, 480, 0.0)]
    assert fake.scrolls == [-600]


def test_click_at_supports_double_click(monkeypatch) -> None:
    fake = _FakePyAutoGui()
    monkeypatch.setattr(desktop, "_load_pyautogui", lambda: fake)

    desktop.click_at(100, 200, button="left", clicks=2)

    assert fake.clicks == [(100, 200, "left", 2)]


def test_type_text_delegates_to_pyautogui(monkeypatch) -> None:
    fake = _FakePyAutoGui()
    monkeypatch.setattr(desktop, "_load_pyautogui", lambda: fake)

    desktop.type_text("astrid", interval=0.05)

    assert fake.writes == [("astrid", 0.05)]


def test_send_hotkey_delegates_to_pyautogui(monkeypatch) -> None:
    fake = _FakePyAutoGui()
    monkeypatch.setattr(desktop, "_load_pyautogui", lambda: fake)

    desktop.send_hotkey("ctrl", "v")

    assert fake.hotkeys == [("ctrl", "v")]


def test_press_key_delegates_to_pyautogui(monkeypatch) -> None:
    fake = _FakePyAutoGui()
    monkeypatch.setattr(desktop, "_load_pyautogui", lambda: fake)

    desktop.press_key("enter")

    assert fake.presses == ["enter"]


def test_take_screenshot_creates_parent_and_saves(monkeypatch, tmp_path: Path) -> None:
    fake = _FakePyAutoGui()
    monkeypatch.setattr(desktop, "_load_pyautogui", lambda: fake)
    target = tmp_path / "shots" / "screen.png"

    path = desktop.take_screenshot(target, region=(1, 2, 3, 4))

    assert path == str(target)
    assert target.parent.exists()
    assert fake.screenshot_calls[0][0] == (1, 2, 3, 4)
    assert fake.screenshot_calls[0][1].saved_path == str(target)
