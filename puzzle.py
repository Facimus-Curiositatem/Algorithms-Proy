"""
puzzle.py — Domain model for Shikaku.

Exports
-------
Clue        Frozen dataclass representing a numbered cell.
Rectangle   Frozen dataclass for an axis-aligned rectangle (half-open coords).
Puzzle      The validated puzzle state (grid dimensions + clues).
Solution    A complete or partial assignment of rectangles to clues.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Clue
# ---------------------------------------------------------------------------

@dataclass(frozen=True, order=True)
class Clue:
    """A numbered cell in the puzzle grid.

    Attributes
    ----------
    row, col : int
        0-indexed position of the clue inside the grid.
    value : int
        The area that the rectangle covering this clue must have.
    """
    row:   int
    col:   int
    value: int

    def __repr__(self) -> str:
        return f"Clue({self.value} @ ({self.row},{self.col}))"


# ---------------------------------------------------------------------------
# Rectangle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rectangle:
    """Axis-aligned rectangle using *half-open* coordinates.

    Covers rows  ``[r0, r1)``  and columns  ``[c0, c1)``.
    This matches Python slicing semantics and eliminates ±1 arithmetic.

    Attributes
    ----------
    r0, c0 : int  Top-left corner (inclusive).
    r1, c1 : int  Bottom-right corner (exclusive).
    """
    r0: int
    c0: int
    r1: int
    c1: int

    # --- derived properties -----------------------------------------------

    @property
    def height(self) -> int:
        return self.r1 - self.r0

    @property
    def width(self) -> int:
        return self.c1 - self.c0

    @property
    def area(self) -> int:
        return self.height * self.width

    # --- spatial queries --------------------------------------------------

    def cells(self) -> Iterator[Tuple[int, int]]:
        """Yield every (row, col) pair inside the rectangle."""
        for r in range(self.r0, self.r1):
            for c in range(self.c0, self.c1):
                yield (r, c)

    def cell_set(self) -> frozenset:
        """Return all cells as a frozenset for O(area) membership tests."""
        return frozenset(self.cells())

    def contains(self, row: int, col: int) -> bool:
        """True iff (row, col) lies inside this rectangle."""
        return self.r0 <= row < self.r1 and self.c0 <= col < self.c1

    def overlaps(self, other: "Rectangle") -> bool:
        """True iff this rectangle shares at least one cell with *other*."""
        return (
            self.r0 < other.r1 and self.r1 > other.r0 and
            self.c0 < other.c1 and self.c1 > other.c0
        )

    def __repr__(self) -> str:
        return (
            f"Rect(rows=[{self.r0},{self.r1}) "
            f"cols=[{self.c0},{self.c1}) area={self.area})"
        )


# ---------------------------------------------------------------------------
# Puzzle
# ---------------------------------------------------------------------------

class Puzzle:
    """Validated Shikaku puzzle.

    Parameters
    ----------
    rows, cols : int
        Grid dimensions (must be ≥ 1).
    clues : list[Clue]
        All numbered cells. Validation checks ``Σ clue.value == rows * cols``.

    Attributes
    ----------
    rows, cols : int
    clues : tuple[Clue, ...]  — immutable after construction.
    """

    def __init__(self, rows: int, cols: int, clues: List[Clue]) -> None:
        self.rows:  int              = rows
        self.cols:  int              = cols
        self.clues: Tuple[Clue, ...] = tuple(clues)
        self.validate()

    # --- construction helper ----------------------------------------------

    @classmethod
    def from_grid(cls, grid: List[List[int]]) -> "Puzzle":
        """Build a Puzzle from a 2D list (0 = empty cell, n>0 = clue value).

        Raises ValueError if the grid is malformed or fails sum validation.
        """
        if not grid or not grid[0]:
            raise ValueError("Grid cannot be empty.")
        rows = len(grid)
        cols = len(grid[0])
        for r, row in enumerate(grid):
            if len(row) != cols:
                raise ValueError(
                    f"Row {r} has {len(row)} columns, expected {cols}."
                )
        clues = [
            Clue(r, c, grid[r][c])
            for r in range(rows)
            for c in range(cols)
            if grid[r][c] > 0
        ]
        return cls(rows, cols, clues)

    # --- validation -------------------------------------------------------

    def validate(self) -> None:
        """Raise ValueError if the puzzle is structurally invalid."""
        if self.rows < 1 or self.cols < 1:
            raise ValueError("Grid dimensions must be at least 1×1.")
        for clue in self.clues:
            if not (0 <= clue.row < self.rows and 0 <= clue.col < self.cols):
                raise ValueError(
                    f"{clue} is outside the {self.rows}×{self.cols} grid."
                )
            if clue.value < 1:
                raise ValueError(
                    f"Clue value must be ≥ 1, got {clue.value}."
                )
        total    = sum(c.value for c in self.clues)
        expected = self.rows * self.cols
        if total != expected:
            raise ValueError(
                f"Sum of clue values ({total}) must equal "
                f"rows × cols ({self.rows}×{self.cols} = {expected})."
            )

    # --- helpers ----------------------------------------------------------

    def clue_at(self, row: int, col: int) -> Optional[Clue]:
        """Return the Clue at (row, col), or None if the cell is empty."""
        for clue in self.clues:
            if clue.row == row and clue.col == col:
                return clue
        return None

    def in_bounds(self, r0: int, c0: int, r1: int, c1: int) -> bool:
        """True iff the rectangle [r0,r1) × [c0,c1) fits inside the grid."""
        return r0 >= 0 and c0 >= 0 and r1 <= self.rows and c1 <= self.cols

    def __repr__(self) -> str:
        return (
            f"Puzzle({self.rows}×{self.cols}, "
            f"{len(self.clues)} clues, "
            f"sum={sum(c.value for c in self.clues)})"
        )

    def __str__(self) -> str:
        cell: Dict[Tuple[int, int], str] = {
            (c.row, c.col): str(c.value) for c in self.clues
        }
        lines = []
        for r in range(self.rows):
            lines.append(
                " ".join(cell.get((r, c), ".") for c in range(self.cols))
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Solution
# ---------------------------------------------------------------------------

class Solution:
    """A (possibly partial) assignment of rectangles to clues.

    Parameters
    ----------
    placements : dict[Clue, Rectangle] | list[tuple[Clue, Rectangle]] | None
        Initial assignments.  Pass nothing or ``None`` for an empty solution.
    """

    def __init__(
        self,
        placements: Optional[
            "Dict[Clue, Rectangle] | List[Tuple[Clue, Rectangle]]"
        ] = None,
    ) -> None:
        if placements is None:
            self._map: Dict[Clue, Rectangle] = {}
        elif isinstance(placements, dict):
            self._map = dict(placements)
        else:
            self._map = dict(placements)

    # --- dict-like interface ----------------------------------------------

    def assign(self, clue: Clue, rect: Rectangle) -> None:
        """Add or overwrite the rectangle for *clue*."""
        self._map[clue] = rect

    def unassign(self, clue: Clue) -> None:
        """Remove the assignment for *clue* (no-op if absent)."""
        self._map.pop(clue, None)

    def get(self, clue: Clue) -> Optional[Rectangle]:
        """Return the rectangle assigned to *clue*, or None."""
        return self._map.get(clue)

    def __contains__(self, clue: object) -> bool:
        return clue in self._map

    def __len__(self) -> int:
        return len(self._map)

    def items(self):
        return self._map.items()

    def copy(self) -> "Solution":
        return Solution(dict(self._map))

    # --- validation -------------------------------------------------------

    def is_complete(self, puzzle: Puzzle) -> bool:
        """True iff every clue in *puzzle* has been assigned a rectangle."""
        return len(self._map) == len(puzzle.clues) and all(
            c in self._map for c in puzzle.clues
        )

    def is_valid(self, puzzle: Puzzle) -> bool:
        """True iff this solution is complete and forms a valid partition.

        Checks:
        1. Every clue has a rectangle.
        2. Each rectangle's area equals its clue's value.
        3. Each rectangle contains exactly its own clue (no foreign clue inside).
        4. No two rectangles overlap.
        5. Every cell of the grid is covered.
        """
        if not self.is_complete(puzzle):
            return False

        rects = list(self._map.values())

        # (2) area & (3) clue containment
        for clue, rect in self._map.items():
            if rect.area != clue.value:
                return False
            if not rect.contains(clue.row, clue.col):
                return False
            for other in puzzle.clues:
                if other is not clue and rect.contains(other.row, other.col):
                    return False

        # (4) pairwise non-overlap
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if rects[i].overlaps(rects[j]):
                    return False

        # (5) full coverage
        covered = set()
        for rect in rects:
            covered.update(rect.cells())
        expected = {
            (r, c)
            for r in range(puzzle.rows)
            for c in range(puzzle.cols)
        }
        return covered == expected

    # --- display ----------------------------------------------------------

    def label_grid(self, puzzle: Puzzle) -> List[List[Optional[int]]]:
        """Return a rows×cols grid where each cell holds a 1-based rectangle
        index (ordered by ``puzzle.clues``) or None if uncovered."""
        grid: List[List[Optional[int]]] = [
            [None] * puzzle.cols for _ in range(puzzle.rows)
        ]
        for idx, clue in enumerate(puzzle.clues, start=1):
            rect = self._map.get(clue)
            if rect is not None:
                for r, c in rect.cells():
                    grid[r][c] = idx
        return grid

    def __str__(self) -> str:
        lines = [f"Solution ({len(self._map)} rectangles):"]
        for clue, rect in self._map.items():
            lines.append(f"  {clue}  →  {rect}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Solution({len(self._map)} placements)"
