"""Workspace containment and the tool surface.

`_safe_path` is the only thing standing between a model-chosen path and the
rest of the filesystem, so it gets the most attention here.
"""

import pytest

from app.tools.registry import (
    ToolError,
    git_diff,
    git_status,
    list_files,
    read_file,
    run_shell,
    search_code,
    write_file,
)


@pytest.mark.parametrize(
    "path",
    ["../outside.txt", "../../etc/passwd", "sub/../../outside.txt", "/etc/passwd"],
)
def test_reads_cannot_escape_the_workspace(context, path):
    with pytest.raises(ToolError, match="escapes"):
        read_file(context, path)


@pytest.mark.parametrize("path", ["../outside.txt", "/tmp/friday-escape.txt"])
def test_writes_cannot_escape_the_workspace(context, path):
    with pytest.raises(ToolError, match="escapes"):
        write_file(context, path, "payload")


def test_write_then_read_round_trip(context, workspace):
    result = write_file(context, "pkg/module.py", "x = 1\n")

    assert "pkg/module.py" in result.replace("\\", "/")
    assert (workspace / "pkg" / "module.py").read_text() == "x = 1\n"
    assert read_file(context, "pkg/module.py") == "x = 1\n"


def test_read_file_rejects_a_missing_path(context):
    with pytest.raises(ToolError, match="does not exist"):
        read_file(context, "nope.txt")


def test_read_file_honours_the_size_limit(context, workspace):
    (workspace / "big.txt").write_text("a" * 1001, encoding="utf-8")

    with pytest.raises(ToolError, match="size limit"):
        read_file(context, "big.txt")


def test_list_files_marks_types_and_skips_noise(context, workspace):
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text("pass\n", encoding="utf-8")
    (workspace / "readme.md").write_text("hi\n", encoding="utf-8")
    (workspace / "__pycache__").mkdir()

    listing = list_files(context, ".")

    assert "[DIR] src" in listing
    assert "[FILE] readme.md" in listing
    assert "__pycache__" not in listing


def test_list_files_rejects_a_file_path(context, workspace):
    (workspace / "readme.md").write_text("hi\n", encoding="utf-8")

    with pytest.raises(ToolError, match="Not a directory"):
        list_files(context, "readme.md")


def test_search_code_reports_path_line_and_text(context, workspace):
    (workspace / "app.py").write_text("import os\nTOKEN = 'secret'\n", encoding="utf-8")

    assert "app.py:2:" in search_code(context, "TOKEN")
    assert search_code(context, "token"), "search should be case-insensitive"
    assert search_code(context, "no-such-string") == "(no matches)"


def test_git_status_and_diff_reflect_the_working_tree(context, git_workspace):
    assert "main" in git_status(context)
    assert git_diff(context) == "(no diff)"

    (git_workspace / "tracked.txt").write_text("changed\n", encoding="utf-8")

    assert "tracked.txt" in git_status(context)
    diff = git_diff(context)
    assert "-original" in diff and "+changed" in diff


def test_run_shell_reports_exit_code_and_output(context):
    assert "exit_code=0" in run_shell(context, "echo friday")
    assert "friday" in run_shell(context, "echo friday")
    assert "exit_code=3" in run_shell(context, "exit 3")


def test_run_shell_starts_in_the_workspace(context, workspace):
    assert str(workspace) in run_shell(context, "pwd")
