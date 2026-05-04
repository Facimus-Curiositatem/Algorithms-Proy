"""
greedy_solver.py
================

Synthetic Shikaku solver based on a greedy construction strategy.

The solver keeps the same public shape used by the rest of the project:

    solver = GreedyShikakuSolver(puzzle)
    solution = solver.solve(time_limit=30.0)
    stats = solver.stats

This implementation is deterministic and does not perform backtracking. At each
step it chooses the most constrained remaining clue and assigns the candidate
rectangle that causes the smallest immediate conflict with the remaining clues.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterator, List, Optional, Set, Tuple

from puzzle import Clue, Puzzle, Rectangle, Solution


Cell = Tuple[int, int]


@dataclass(frozen=True)
class GreedySolverStats:
    """Execution statistics for the greedy solver."""

    candidates_total: int = 0
    nodes_visited: int = 0
    backtracks: int = 0
    elapsed_seconds: float = 0.0


class GreedyShikakuSolver:
    """Greedy Shikaku solver.

    The algorithm builds a solution one rectangle at a time.

    At each step:

    1. It computes the feasible candidates for every unassigned clue.
    2. It selects the clue with the smallest number of feasible candidates.
    3. It assigns the rectangle that eliminates the fewest future candidates.
    4. It commits the choice permanently.

    This strategy is fast, but it is not complete. If a locally good decision
    blocks a later clue, the solver returns `None` instead of backtracking.
    """

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle: Puzzle = puzzle
        self._candidates: Dict[Clue, Tuple[Rectangle, ...]] = {}
        self._rect_cells: Dict[Rectangle, FrozenSet[Cell]] = {}
        self._stats: GreedySolverStats = GreedySolverStats()
        self._nodes_visited: int = 0
        self._candidates_total: int = 0

    @property
    def stats(self) -> GreedySolverStats:
        """Return the latest solver statistics."""
        return self._stats

    def solve(self, time_limit: float = 60.0) -> Optional[Solution]:
        """Try to solve the puzzle using a greedy heuristic.

        Parameters
        ----------
        time_limit:
            Maximum wall-clock time in seconds.

        Returns
        -------
        Optional[Solution]
            A valid solution if the greedy construction succeeds; otherwise
            `None`.
        """
        start = time.perf_counter()
        deadline = start + time_limit

        self._nodes_visited = 0
        self._candidates = self._generate_candidates()
        self._rect_cells = {
            rect: rect.cell_set()
            for candidates in self._candidates.values()
            for rect in candidates
        }
        self._candidates_total = sum(
            len(candidates) for candidates in self._candidates.values()
        )

        result = self._construct(deadline)

        elapsed = time.perf_counter() - start
        self._stats = GreedySolverStats(
            candidates_total=self._candidates_total,
            nodes_visited=self._nodes_visited,
            backtracks=0,
            elapsed_seconds=elapsed,
        )
        return result

    # ------------------------------------------------------------------
    # Candidate generation
    # ------------------------------------------------------------------
    def _generate_candidates(self) -> Dict[Clue, Tuple[Rectangle, ...]]:
        """Generate all statically valid rectangles for each clue."""
        result: Dict[Clue, Tuple[Rectangle, ...]] = {}

        for clue in self.puzzle.clues:
            candidates: List[Rectangle] = []

            for height, width in self._factor_pairs(clue.value):
                if height > self.puzzle.rows or width > self.puzzle.cols:
                    continue

                min_r0 = max(0, clue.row - height + 1)
                max_r0 = min(clue.row, self.puzzle.rows - height)
                min_c0 = max(0, clue.col - width + 1)
                max_c0 = min(clue.col, self.puzzle.cols - width)

                for r0 in range(min_r0, max_r0 + 1):
                    for c0 in range(min_c0, max_c0 + 1):
                        rect = Rectangle(r0, c0, r0 + height, c0 + width)

                        if self._contains_foreign_clue(clue, rect):
                            continue

                        candidates.append(rect)

            result[clue] = tuple(candidates)

        return result

    @staticmethod
    def _factor_pairs(value: int) -> Iterator[Tuple[int, int]]:
        """Yield all positive factor pairs `(height, width)` for `value`."""
        for height in range(1, value + 1):
            if value % height == 0:
                yield height, value // height

    def _contains_foreign_clue(self, owner: Clue, rect: Rectangle) -> bool:
        """Return True if `rect` contains a clue different from `owner`."""
        for clue in self.puzzle.clues:
            if clue != owner and rect.contains(clue.row, clue.col):
                return True
        return False

    # ------------------------------------------------------------------
    # Greedy construction
    # ------------------------------------------------------------------
    def _construct(self, deadline: float) -> Optional[Solution]:
        """Build a solution using irreversible local decisions."""
        remaining: Set[Clue] = set(self.puzzle.clues)
        occupied: Set[Cell] = set()
        placements: List[Tuple[Clue, Rectangle]] = []

        while remaining:
            if time.perf_counter() >= deadline:
                return None

            feasible_by_clue = self._feasible_candidates_by_clue(
                remaining=remaining,
                occupied=occupied,
            )

            if any(len(candidates) == 0 for candidates in feasible_by_clue.values()):
                return None

            clue = self._select_most_constrained_clue(feasible_by_clue)
            rect = self._select_best_rectangle(
                clue=clue,
                candidates=feasible_by_clue[clue],
                remaining=remaining,
                occupied=occupied,
            )

            if rect is None:
                return None

            rect_cells = self._rect_cells[rect]
            placements.append((clue, rect))
            occupied.update(rect_cells)
            remaining.remove(clue)

        solution = Solution(self.puzzle, placements)
        if solution.is_valid():
            return solution
        return None

    def _feasible_candidates_by_clue(
        self,
        remaining: Set[Clue],
        occupied: Set[Cell],
    ) -> Dict[Clue, Tuple[Rectangle, ...]]:
        """Return candidates that do not overlap the currently occupied cells."""
        feasible: Dict[Clue, Tuple[Rectangle, ...]] = {}

        for clue in remaining:
            valid: List[Rectangle] = []
            for rect in self._candidates[clue]:
                self._nodes_visited += 1
                if self._rect_cells[rect].isdisjoint(occupied):
                    valid.append(rect)
            feasible[clue] = tuple(valid)

        return feasible

    @staticmethod
    def _select_most_constrained_clue(
        feasible_by_clue: Dict[Clue, Tuple[Rectangle, ...]],
    ) -> Clue:
        """Select the remaining clue with the smallest feasible domain."""
        return min(
            feasible_by_clue,
            key=lambda clue: (len(feasible_by_clue[clue]), clue.row, clue.col),
        )

    def _select_best_rectangle(
        self,
        clue: Clue,
        candidates: Tuple[Rectangle, ...],
        remaining: Set[Clue],
        occupied: Set[Cell],
    ) -> Optional[Rectangle]:
        """Choose the candidate with the smallest immediate conflict score."""
        best_rect: Optional[Rectangle] = None
        best_score: Optional[Tuple[int, int, int, int, int]] = None

        future_clues = remaining - {clue}

        for rect in candidates:
            score = self._candidate_score(
                rect=rect,
                future_clues=future_clues,
                occupied=occupied,
            )

            if best_score is None or score < best_score:
                best_score = score
                best_rect = rect

        return best_rect

    def _candidate_score(
        self,
        rect: Rectangle,
        future_clues: Set[Clue],
        occupied: Set[Cell],
    ) -> Tuple[int, int, int, int, int]:
        """Return a lexicographic score for a greedy candidate.

        Lower scores are better.

        The score prioritizes:

        1. Fewer future candidate eliminations.
        2. Fewer future clues left with a single option.
        3. More compact rectangles.
        4. Earlier row.
        5. Earlier column.
        """
        new_occupied = set(occupied)
        new_occupied.update(self._rect_cells[rect])

        eliminated = 0
        forced_future_clues = 0

        for future_clue in future_clues:
            remaining_options = 0

            for future_rect in self._candidates[future_clue]:
                if self._rect_cells[future_rect].isdisjoint(new_occupied):
                    remaining_options += 1
                else:
                    eliminated += 1

            if remaining_options == 1:
                forced_future_clues += 1

        compactness = rect.height + rect.width

        return (
            eliminated,
            forced_future_clues,
            compactness,
            rect.r0,
            rect.c0,
        )
