"""
solver.py — Synthetic Shikaku solver.

This module implements a CSP-based solver for Shikaku puzzles. The solver is
kept independent from the GUI and parser layers: it only depends on the domain
model defined in puzzle.py.
"""

from __future__ import annotations

import time
from math import isqrt
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from puzzle import Clue, Puzzle, Rectangle, Solution


Cell = Tuple[int, int]
Placement = Tuple[Clue, Rectangle]


@dataclass
class SolverStats:
    """Execution statistics collected during one solve invocation."""

    candidates_total: int = 0
    nodes_visited: int = 0
    backtracks: int = 0
    elapsed_seconds: float = 0.0


class ShikakuSolver:
    """Solve a Shikaku puzzle using CSP backtracking.

    The CSP model is:

    - Variables: puzzle clues.
    - Domains: valid rectangles for each clue.
    - Constraints: rectangle area, clue containment, no foreign clue inside,
      no overlap between selected rectangles, and full grid coverage.

    Search uses dynamic Minimum Remaining Values (MRV), forward checking, and
    a reachability check over uncovered cells.
    """

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self._stats = SolverStats()
        self._candidates: Dict[Clue, Tuple[Rectangle, ...]] = {}
        self._rect_cells: Dict[Rectangle, FrozenSet[Cell]] = {}
        self._all_cells: FrozenSet[Cell] = frozenset(
            (r, c)
            for r in range(self.puzzle.rows)
            for c in range(self.puzzle.cols)
        )

    @property
    def stats(self) -> SolverStats:
        """Return statistics for the latest solve invocation."""
        return self._stats

    def solve(self, time_limit: float = 60.0) -> Optional[Solution]:
        """Return a valid solution if one is found within *time_limit*.

        Parameters
        ----------
        time_limit : float
            Wall-clock budget in seconds.

        Returns
        -------
        Optional[Solution]
            A valid solution, or None if no solution is found within the time
            budget.
        """
        start = time.perf_counter()
        deadline = start + max(0.0, time_limit)
        self._stats = SolverStats()
        self._candidates = self._generate_all_candidates()
        self._stats.candidates_total = sum(
            len(rects) for rects in self._candidates.values()
        )

        if any(len(rects) == 0 for rects in self._candidates.values()):
            self._stats.elapsed_seconds = time.perf_counter() - start
            return None

        remaining = tuple(self.puzzle.clues)
        result = self._backtrack(
            remaining=remaining,
            occupied=frozenset(),
            placements=(),
            deadline=deadline,
        )
        self._stats.elapsed_seconds = time.perf_counter() - start
        return result

    # ------------------------------------------------------------------
    # Candidate generation
    # ------------------------------------------------------------------
    def _generate_all_candidates(self) -> Dict[Clue, Tuple[Rectangle, ...]]:
        candidates: Dict[Clue, Tuple[Rectangle, ...]] = {}
        for clue in self.puzzle.clues:
            rects = tuple(self._generate_candidates_for_clue(clue))
            candidates[clue] = rects
            for rect in rects:
                if rect not in self._rect_cells:
                    self._rect_cells[rect] = frozenset(rect.cells())
        return candidates

    def _generate_candidates_for_clue(self, clue: Clue) -> List[Rectangle]:
        rects: List[Rectangle] = []

        for height, width in self._factor_pairs(clue.value):
            if height > self.puzzle.rows or width > self.puzzle.cols:
                continue

            r0_min = max(0, clue.row - height + 1)
            r0_max = min(clue.row, self.puzzle.rows - height)
            c0_min = max(0, clue.col - width + 1)
            c0_max = min(clue.col, self.puzzle.cols - width)

            for r0 in range(r0_min, r0_max + 1):
                for c0 in range(c0_min, c0_max + 1):
                    rect = Rectangle(r0, c0, r0 + height, c0 + width)
                    if self._contains_only_this_clue(rect, clue):
                        rects.append(rect)

        return rects

    @staticmethod
    def _factor_pairs(value: int) -> Iterable[Tuple[int, int]]:
        for height in range(1, isqrt(value) + 1):
            if value % height != 0:
                continue

            width = value // height
            yield height, width

            if height != width:
                yield width, height

    def _contains_only_this_clue(self, rect: Rectangle, clue: Clue) -> bool:
        if not rect.contains(clue.row, clue.col):
            return False

        for other in self.puzzle.clues:
            if other != clue and rect.contains(other.row, other.col):
                return False

        return True

    # ------------------------------------------------------------------
    # Backtracking search
    # ------------------------------------------------------------------
    def _backtrack(
        self,
        remaining: Tuple[Clue, ...],
        occupied: FrozenSet[Cell],
        placements: Tuple[Placement, ...],
        deadline: float,
    ) -> Optional[Solution]:
        if time.perf_counter() > deadline:
            return None

        self._stats.nodes_visited += 1

        if not remaining:
            solution = Solution(self.puzzle, placements)
            return solution if solution.is_valid() else None

        selected, options = self._select_mrv_variable(remaining, occupied)
        if selected is None:
            return None

        next_remaining = tuple(clue for clue in remaining if clue != selected)

        for rect in self._order_values(options, next_remaining, occupied):
            rect_cells = self._rect_cells[rect]
            if rect_cells & occupied:
                continue

            next_occupied = occupied | rect_cells

            if not self._forward_check(next_remaining, next_occupied):
                self._stats.backtracks += 1
                continue

            if not self._uncovered_cells_are_reachable(
                next_remaining,
                next_occupied,
            ):
                self._stats.backtracks += 1
                continue

            result = self._backtrack(
                remaining=next_remaining,
                occupied=next_occupied,
                placements=placements + ((selected, rect),),
                deadline=deadline,
            )

            if result is not None:
                return result

            self._stats.backtracks += 1

        return None

    def _select_mrv_variable(
        self,
        remaining: Sequence[Clue],
        occupied: FrozenSet[Cell],
    ) -> Tuple[Optional[Clue], Tuple[Rectangle, ...]]:
        best_clue: Optional[Clue] = None
        best_options: Tuple[Rectangle, ...] = ()

        for clue in remaining:
            available = tuple(
                rect
                for rect in self._candidates[clue]
                if not (self._rect_cells[rect] & occupied)
            )

            if not available:
                return None, ()

            if best_clue is None or len(available) < len(best_options):
                best_clue = clue
                best_options = available

        return best_clue, best_options

    def _order_values(
        self,
        options: Tuple[Rectangle, ...],
        remaining: Sequence[Clue],
        occupied: FrozenSet[Cell],
    ) -> Tuple[Rectangle, ...]:
        return tuple(
            sorted(
                options,
                key=lambda rect: self._candidate_conflict_count(
                    rect,
                    remaining,
                    occupied,
                ),
            )
        )

    def _candidate_conflict_count(
        self,
        rect: Rectangle,
        remaining: Sequence[Clue],
        occupied: FrozenSet[Cell],
    ) -> int:
        next_occupied = occupied | self._rect_cells[rect]
        conflicts = 0

        for clue in remaining:
            for candidate in self._candidates[clue]:
                if self._rect_cells[candidate] & next_occupied:
                    conflicts += 1

        return conflicts

    def _forward_check(
        self,
        remaining: Sequence[Clue],
        occupied: FrozenSet[Cell],
    ) -> bool:
        for clue in remaining:
            if not any(
                not (self._rect_cells[rect] & occupied)
                for rect in self._candidates[clue]
            ):
                return False

        return True

    def _uncovered_cells_are_reachable(
        self,
        remaining: Sequence[Clue],
        occupied: FrozenSet[Cell],
    ) -> bool:
        uncovered = self._all_cells - occupied

        if not uncovered:
            return True

        reachable: Set[Cell] = set()
        for clue in remaining:
            for rect in self._candidates[clue]:
                rect_cells = self._rect_cells[rect]
                if rect_cells & occupied:
                    continue
                reachable.update(rect_cells)

        return uncovered <= reachable
