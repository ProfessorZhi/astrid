from __future__ import annotations

from io import StringIO

from astrid.tui.screen_diff import LineDiffScreenWriter


def test_line_diff_writer_clears_shorter_replacement_rows() -> None:
    output = StringIO()
    writer = LineDiffScreenWriter(output)

    writer.render("alpha\nlong trailing text")
    output.seek(0)
    output.truncate(0)

    rendered = writer.render("alpha\nshort")

    assert "\x1b[2J\x1b[H" not in rendered
    assert "\x1b[2;1H\x1b[2Kshort" in rendered
    assert output.getvalue() == rendered


def test_line_diff_writer_clears_rows_removed_by_next_frame() -> None:
    writer = LineDiffScreenWriter(StringIO())

    writer.render("one\ntwo\nthree")
    rendered = writer.render("one")

    assert "\x1b[2;1H\x1b[2K" in rendered
    assert "\x1b[3;1H\x1b[2K" in rendered
    assert "two" not in rendered
    assert "three" not in rendered


def test_line_diff_writer_force_full_redraw_clears_screen_again() -> None:
    writer = LineDiffScreenWriter(StringIO())

    writer.render("one\ntwo")
    rendered = writer.render("one\nTWO", force_full=True)

    assert rendered.startswith("\x1b[2J\x1b[H")
    assert "one\nTWO" in rendered
