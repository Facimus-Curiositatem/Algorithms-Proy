"""
brute_force_solver.py
=====================

Synthetic Shikaku solver based on exhaustive search over the rectangle
candidate space.

The solver keeps the same public shape used by the rest of the project:

    solver = BruteForceShikakuSolver(puzzle)
    solution = solver.solve(time_limit=30.0)
    stats = solver.stats

This implementation is intentionally simple. It generates all valid rectangle
candidates for each clue and then enumerates every possible combination until a
valid Solution is found or the time limit is reached.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple

from puzzle import Clue, Puzzle, Rectangle, Solution


@dataclass(frozen=True)
class BruteForceSolverStats:
    """Execution statistics for the brute-force solver."""

    candidates_total: int = 0
    nodes_visited: int = 0
    backtracks: int = 0
    elapsed_seconds: float = 0.0


class BruteForceShikakuSolver:
    """Brute-force Shikaku solver.

    The solver treats each clue as a variable and each valid rectangle as a
    candidate value for that variable. Unlike the CSP solver, this version does
    not use MRV, forward checking or partial overlap pruning. It enumerates the
    Cartesian product of all candidate domains and validates complete
    assignments using `Solution.is_valid()`.

    This makes it useful as a baseline for comparing execution time and search
    quality against Greedy, DP and CSP-based approaches.
    """

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle: Puzzle = puzzle
        self._candidates: Dict[Clue, Tuple[Rectangle, ...]] = {}
        self._stats: BruteForceSolverStats = BruteForceSolverStats()
        self._nodes_visited: int = 0
        self._backtracks: int = 0
        self._candidates_total: int = 0

    @property
    def stats(self) -> BruteForceSolverStats:
        """Return the latest solver statistics."""
        return self._stats

    def solve(self, time_limit: float = 60.0) -> Optional[Solution]:
        """Try to solve the puzzle using exhaustive search.

        Parameters
        ----------
        time_limit:
            Maximum wall-clock time in seconds.

        Returns
        -------
        Optional[Solution]
            A valid solution if one is found before the deadline; otherwise
            `None`.
        """
        start = time.perf_counter()
        deadline = start + time_limit

        self._nodes_visited = 0
        self._backtracks = 0
        self._candidates = self._generate_candidates()
        self._candidates_total = sum(
            len(candidates) for candidates in self._candidates.values()
        )

        result: Optional[Solution]
        if any(len(self._candidates[clue]) == 0 for clue in self.puzzle.clues):
            result = None
        else:
            result = self._enumerate(
                clue_index=0,
                placements=[],
                deadline=deadline,
            )

        elapsed = time.perf_counter() - start
        self._stats = BruteForceSolverStats(
            candidates_total=self._candidates_total,
            nodes_visited=self._nodes_visited,
            backtracks=self._backtracks,
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
    # Exhaustive enumeration
    # ------------------------------------------------------------------
    def _enumerate(
        self,
        clue_index: int,
        placements: List[Tuple[Clue, Rectangle]],
        deadline: float,
    ) -> Optional[Solution]:
        """Enumerate every complete assignment in clue order."""
        if time.perf_counter() >= deadline:
            return None

        if clue_index == len(self.puzzle.clues):
            self._nodes_visited += 1
            solution = Solution(self.puzzle, placements)

            if solution.is_valid():
                return solution

            self._backtracks += 1
            return None

        clue = self.puzzle.clues[clue_index]

        for rect in self._candidates[clue]:
            placements.append((clue, rect))
            result = self._enumerate(
                clue_index=clue_index + 1,
                placements=placements,
                deadline=deadline,
            )
            if result is not None:
                return result
            placements.pop()

            if time.perf_counter() >= deadline:
                return None

        return None
