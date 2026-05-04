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
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Tuple, Union


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

# ---------------------------------------------------------------------------
# Solution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Solution:
    """Immutable assignment of rectangles to clues for a specific puzzle.

    Parameters
    ----------
    puzzle : Puzzle
        Puzzle instance solved by this solution.
    placements : mapping or iterable of tuple[Clue, Rectangle], optional
        Assignments from clues to rectangles. Each rectangle is expected to
        cover exactly one clue, match its clue value as area, and not overlap
        any other rectangle.

    Notes
    -----
    The class is immutable: operations that conceptually modify the solution
    return a new `Solution` instance instead of mutating the current one.
    """

    puzzle: Puzzle
    placements: Tuple[Tuple[Clue, Rectangle], ...]

    def __init__(
        self,
        puzzle: Puzzle,
        placements: Optional[
            Union[
                Mapping[Clue, Rectangle],
                Iterable[Tuple[Clue, Rectangle]],
            ]
        ] = None,
    ) -> None:
        object.__setattr__(self, "puzzle", puzzle)

        if placements is None:
            normalized: Tuple[Tuple[Clue, Rectangle], ...] = ()
        elif isinstance(placements, Mapping):
            normalized = tuple(placements.items())
        else:
            normalized = tuple(placements)

        object.__setattr__(self, "placements", normalized)

    # --- dict-like read interface -----------------------------------------

    @property
    def assignment_map(self) -> Dict[Clue, Rectangle]:
        """Return the assignments as a dictionary.

        A new dictionary is returned to preserve the immutability of the
        `Solution` object.
        """
        return dict(self.placements)

    def get(self, clue: Clue) -> Optional[Rectangle]:
        """Return the rectangle assigned to *clue*, or None."""
        return self.assignment_map.get(clue)

    def __contains__(self, clue: object) -> bool:
        return clue in self.assignment_map

    def __len__(self) -> int:
        return len(self.placements)

    def items(self) -> Tuple[Tuple[Clue, Rectangle], ...]:
        """Return the placement pairs in their stored order."""
        return self.placements

    def copy(self) -> "Solution":
        """Return a logically equivalent solution.

        Since the class is immutable, returning a new instance is mostly useful
        for API symmetry with older mutable versions.
        """
        return Solution(self.puzzle, self.placements)

    # --- immutable update helpers -----------------------------------------

    def with_assignment(self, clue: Clue, rect: Rectangle) -> "Solution":
        """Return a new solution with *clue* assigned to *rect*.

        If the clue was already assigned, its previous rectangle is replaced.
        """
        updated = [
            (current_clue, current_rect)
            for current_clue, current_rect in self.placements
            if current_clue != clue
        ]
        updated.append((clue, rect))
        return Solution(self.puzzle, updated)

    def without_assignment(self, clue: Clue) -> "Solution":
        """Return a new solution without the assignment for *clue*."""
        updated = [
            (current_clue, current_rect)
            for current_clue, current_rect in self.placements
            if current_clue != clue
        ]
        return Solution(self.puzzle, updated)

    # --- validation -------------------------------------------------------

    def is_complete(self) -> bool:
        """True iff every clue in the puzzle has exactly one rectangle."""
        assignment = self.assignment_map

        if len(assignment) != len(self.placements):
            return False

        return (
            len(assignment) == len(self.puzzle.clues)
            and all(clue in assignment for clue in self.puzzle.clues)
        )

    def is_valid(self) -> bool:
        """True iff this solution forms a valid Shikaku partition.

        Checks:
        1. Every clue has exactly one rectangle.
        2. Each rectangle fits inside the puzzle grid.
        3. Each rectangle's area equals its clue's value.
        4. Each rectangle contains its own clue.
        5. Each rectangle contains no foreign clue.
        6. No two rectangles overlap.
        7. Every cell of the grid is covered.
        """
        if not self.is_complete():
            return False

        assignment = self.assignment_map
        rects = list(assignment.values())

        # (2), (3), (4), (5): local rectangle validity
        for clue, rect in assignment.items():
            if not self.puzzle.in_bounds(rect.r0, rect.c0, rect.r1, rect.c1):
                return False

            if rect.area != clue.value:
                return False

            if not rect.contains(clue.row, clue.col):
                return False

            for other in self.puzzle.clues:
                if other != clue and rect.contains(other.row, other.col):
                    return False

        # (6): pairwise non-overlap
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if rects[i].overlaps(rects[j]):
                    return False

        # (7): full grid coverage
        covered = set()
        for rect in rects:
            covered.update(rect.cells())

        expected = {
            (r, c)
            for r in range(self.puzzle.rows)
            for c in range(self.puzzle.cols)
        }

        return covered == expected

    # --- display ----------------------------------------------------------

    def label_grid(self) -> List[List[Optional[int]]]:
        """Return a rows×cols grid with one 1-based label per rectangle.

        Cells not covered by any current placement are returned as None.
        """
        grid: List[List[Optional[int]]] = [
            [None] * self.puzzle.cols for _ in range(self.puzzle.rows)
        ]

        for idx, (_, rect) in enumerate(self.placements, start=1):
            for r, c in rect.cells():
                if 0 <= r < self.puzzle.rows and 0 <= c < self.puzzle.cols:
                    grid[r][c] = idx

        return grid

    def __str__(self) -> str:
        lines = [f"Solution ({len(self.placements)} rectangles):"]
        for clue, rect in self.placements:
            lines.append(f"  {clue}  →  {rect}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"Solution({self.puzzle.rows}×{self.puzzle.cols}, "
            f"{len(self.placements)} placements)"
        )