"""
parser.py
=========
Read and write Shikaku puzzles in a simple text format.

File format
-----------
The first non-empty line contains two integers: ROWS COLS.
The next ROWS lines contain COLS whitespace-separated tokens each.
A token is either a positive integer (a clue) or a dot ('.') for an empty cell.
Lines starting with '#' are treated as comments and skipped.

Example (5x5)::

    # Sample 5x5 puzzle
    5 5
    .  .  3  .  .
    .  .  .  .  4
    6  .  .  .  .
    .  .  .  .  .
    .  .  .  6  6

Saved solutions
---------------
A solution is written as a grid of integer labels (1..N). All cells that
belong to the same rectangle share the same label. Labels are assigned in
the order placements appear in the Solution object.
"""

from __future__ import annotations

import os
from typing import List

from puzzle import Clue, Puzzle, Solution


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------
def load_puzzle(path: str) -> Puzzle:
    """Read a puzzle file and return a `Puzzle` instance."""
    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    lines: List[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)

    if not lines:
        raise ValueError(f"File '{path}' is empty")

    header_parts = lines[0].split()
    if len(header_parts) != 2:
        raise ValueError("First line must contain two integers: ROWS COLS")
    try:
        rows, cols = int(header_parts[0]), int(header_parts[1])
    except ValueError as exc:
        raise ValueError(f"Invalid header in '{path}': {lines[0]}") from exc

    grid_lines = lines[1:1 + rows]
    if len(grid_lines) < rows:
        raise ValueError(
            f"Expected {rows} grid rows but found {len(grid_lines)} in '{path}'"
        )

    clues: List[Clue] = []
    for r, raw in enumerate(grid_lines):
        tokens = raw.split()
        if len(tokens) != cols:
            raise ValueError(
                f"Row {r} of '{path}' has {len(tokens)} tokens, expected {cols}"
            )
        for c, tok in enumerate(tokens):
            if tok == ".":
                continue
            try:
                value = int(tok)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid token '{tok}' at row {r}, col {c}"
                ) from exc
            clues.append(Clue(r, c, value))

    puzzle = Puzzle(rows=rows, cols=cols, clues=clues)
    puzzle.validate()
    return puzzle


# ----------------------------------------------------------------------------
# Saving puzzles
# ----------------------------------------------------------------------------
def save_puzzle(puzzle: Puzzle, path: str) -> None:
    """Write a `Puzzle` to disk using the format documented above."""
    grid: List[List[str]] = [
        ["."] * puzzle.cols for _ in range(puzzle.rows)
    ]
    for clue in puzzle.clues:
        grid[clue.row][clue.col] = str(clue.value)

    cell_w = max((len(t) for row in grid for t in row), default=1)

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{puzzle.rows} {puzzle.cols}\n")
        for row in grid:
            f.write(" ".join(t.rjust(cell_w) for t in row) + "\n")


# ----------------------------------------------------------------------------
# Saving solutions
# ----------------------------------------------------------------------------
def save_solution(solution: Solution, path: str) -> None:
    """Write a `Solution` as a labeled grid (one label per rectangle)."""
    rows, cols = solution.puzzle.rows, solution.puzzle.cols
    labels: List[List[int]] = [[0] * cols for _ in range(rows)]
    for idx, (_, rect) in enumerate(solution.placements, start=1):
        for r, c in rect.cells():
            labels[r][c] = idx
    cell_w = len(str(len(solution.placements)))

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Shikaku solution: {rows}x{cols}, "
                f"{len(solution.placements)} rectangles\n")
        for row in labels:
            f.write(" ".join(str(v).rjust(cell_w) for v in row) + "\n")
