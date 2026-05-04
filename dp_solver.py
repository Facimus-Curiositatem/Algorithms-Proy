"""
dp_solver.py
============

Synthetic Shikaku solver based on top-down dynamic programming with
memoization.

The solver keeps the same public shape used by the rest of the project:

    solver = DPShikakuSolver(puzzle)
    solution = solver.solve(time_limit=30.0)
    stats = solver.stats

In this context, dynamic programming is implemented as memoized search over
states of the form:

    (remaining clues, occupied cells)

The occupied cells are represented with a bitmask, which makes overlap checks
and state hashing efficient.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from math import isqrt
from typing import Dict, Iterator, List, Optional, Set, Tuple

from puzzle import Clue, Puzzle, Rectangle, Solution


Cell = Tuple[int, int]
StateKey = Tuple[Tuple[int, ...], int]


@dataclass(frozen=True)
class DPSolverStats:
    """Execution statistics for the dynamic-programming solver.

    Attributes
    ----------
    candidates_total:
        Total number of statically valid rectangle candidates generated.
    nodes_visited:
        Number of DP states expanded during the search.
    backtracks:
        Number of candidate branches that failed after being explored.
    elapsed_seconds:
        Wall-clock execution time.
    memo_hits:
        Number of times a previously failed state was reused.
    states_memoized:
        Number of failed states stored in the memo table.
    """

    candidates_total: int = 0
    nodes_visited: int = 0
    backtracks: int = 0
    elapsed_seconds: float = 0.0
    memo_hits: int = 0
    states_memoized: int = 0


@dataclass(frozen=True)
class _Candidate:
    """Internal rectangle candidate with its precomputed cell bitmask."""

    rect: Rectangle
    mask: int


class DPShikakuSolver:
    """Shikaku solver using memoized recursive search.

    The algorithm models the puzzle as a state-space problem. A state is
    determined by:

    1. The set of clues that still need a rectangle.
    2. The set of cells that are already occupied.

    Since different search paths can lead to the same state, the solver stores
    failed states in a memo table. If the same state appears again, the solver
    skips it immediately.

    This approach is complete: if the time limit is not reached, it can find a
    valid solution whenever one exists within the generated candidate space.
    """

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle: Puzzle = puzzle
        self._clues: Tuple[Clue, ...] = puzzle.clues
        self._candidates: Dict[int, Tuple[_Candidate, ...]] = {}
        self._failed_states: Set[StateKey] = set()
        self._stats: DPSolverStats = DPSolverStats()

        self._full_mask: int = (1 << (self.puzzle.rows * self.puzzle.cols)) - 1
        self._nodes_visited: int = 0
        self._backtracks: int = 0
        self._memo_hits: int = 0
        self._candidates_total: int = 0
        self._timed_out: bool = False

    @property
    def stats(self) -> DPSolverStats:
        """Return the latest solver statistics."""
        return self._stats

    def solve(self, time_limit: float = 60.0) -> Optional[Solution]:
        """Solve the puzzle using DP with memoization.

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
        self._memo_hits = 0
        self._timed_out = False
        self._failed_states.clear()

        self._candidates = self._generate_candidates()
        self._candidates_total = sum(
            len(candidates) for candidates in self._candidates.values()
        )

        if any(len(self._candidates[index]) == 0 for index in range(len(self._clues))):
            result: Optional[Solution] = None
        else:
            result = self._search(
                remaining=tuple(range(len(self._clues))),
                occupied_mask=0,
                placements=[],
                deadline=deadline,
            )

        elapsed = time.perf_counter() - start
        self._stats = DPSolverStats(
            candidates_total=self._candidates_total,
            nodes_visited=self._nodes_visited,
            backtracks=self._backtracks,
            elapsed_seconds=elapsed,
            memo_hits=self._memo_hits,
            states_memoized=len(self._failed_states),
        )
        return result

    # ------------------------------------------------------------------
    # Candidate generation
    # ------------------------------------------------------------------
    def _generate_candidates(self) -> Dict[int, Tuple[_Candidate, ...]]:
        """Generate all statically valid rectangle candidates for each clue."""
        result: Dict[int, Tuple[_Candidate, ...]] = {}

        for index, clue in enumerate(self._clues):
            candidates: List[_Candidate] = []

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

                        if self._contains_foreign_clue(owner=clue, rect=rect):
                            continue

                        candidates.append(
                            _Candidate(rect=rect, mask=self._rect_mask(rect))
                        )

            result[index] = tuple(candidates)

        return result

    @staticmethod
    def _factor_pairs(value: int) -> Iterator[Tuple[int, int]]:
        """Yield all positive factor pairs `(height, width)` for `value`.

        Both orientations are produced when height and width are different.
        """
        for height in range(1, isqrt(value) + 1):
            if value % height != 0:
                continue

            width = value // height
            yield height, width

            if height != width:
                yield width, height

    def _contains_foreign_clue(self, owner: Clue, rect: Rectangle) -> bool:
        """Return True if `rect` contains a clue different from `owner`."""
        for clue in self._clues:
            if clue != owner and rect.contains(clue.row, clue.col):
                return True
        return False

    def _rect_mask(self, rect: Rectangle) -> int:
        """Convert a rectangle into a bitmask of covered cells."""
        mask = 0

        for row, col in rect.cells():
            bit_index = row * self.puzzle.cols + col
            mask |= 1 << bit_index

        return mask

    # ------------------------------------------------------------------
    # DP search
    # ------------------------------------------------------------------
    def _search(
        self,
        remaining: Tuple[int, ...],
        occupied_mask: int,
        placements: List[Tuple[Clue, Rectangle]],
        deadline: float,
    ) -> Optional[Solution]:
        """Search from a DP state.

        The state is `(remaining, occupied_mask)`. Failed states are stored in
        `self._failed_states`, which prevents repeated exploration of the same
        subproblem.
        """
        if time.perf_counter() >= deadline:
            self._timed_out = True
            return None

        if not remaining:
            self._nodes_visited += 1
            solution = Solution(self.puzzle, placements)
            return solution if solution.is_valid() else None

        state: StateKey = (remaining, occupied_mask)

        if state in self._failed_states:
            self._memo_hits += 1
            return None

        self._nodes_visited += 1

        if not self._all_empty_cells_reachable(
            remaining=remaining,
            occupied_mask=occupied_mask,
        ):
            self._memoize_failed_state(state)
            return None

        selected_index, feasible_candidates = self._select_next_clue(
            remaining=remaining,
            occupied_mask=occupied_mask,
        )

        if selected_index is None or not feasible_candidates:
            self._memoize_failed_state(state)
            return None

        next_remaining = tuple(
            index for index in remaining if index != selected_index
        )

        ordered_candidates = self._order_candidates(
            candidates=feasible_candidates,
            future_indices=next_remaining,
            occupied_mask=occupied_mask,
        )

        selected_clue = self._clues[selected_index]

        for candidate in ordered_candidates:
            placements.append((selected_clue, candidate.rect))

            result = self._search(
                remaining=next_remaining,
                occupied_mask=occupied_mask | candidate.mask,
                placements=placements,
                deadline=deadline,
            )

            if result is not None:
                return result

            placements.pop()

            if self._timed_out:
                return None

            self._backtracks += 1

        self._memoize_failed_state(state)
        return None

    def _memoize_failed_state(self, state: StateKey) -> None:
        """Store a failed state unless the solver has timed out."""
        if not self._timed_out:
            self._failed_states.add(state)

    def _select_next_clue(
        self,
        remaining: Tuple[int, ...],
        occupied_mask: int,
    ) -> Tuple[Optional[int], Tuple[_Candidate, ...]]:
        """Select the remaining clue with the fewest feasible candidates.

        This is the MRV heuristic applied inside the DP recurrence.
        """
        best_index: Optional[int] = None
        best_candidates: Tuple[_Candidate, ...] = ()

        for index in remaining:
            feasible = tuple(
                candidate
                for candidate in self._candidates[index]
                if candidate.mask & occupied_mask == 0
            )

            if best_index is None:
                best_index = index
                best_candidates = feasible
                continue

            current_key = (
                len(feasible),
                self._clues[index].row,
                self._clues[index].col,
            )
            best_key = (
                len(best_candidates),
                self._clues[best_index].row,
                self._clues[best_index].col,
            )

            if current_key < best_key:
                best_index = index
                best_candidates = feasible

        return best_index, best_candidates

    def _all_empty_cells_reachable(
        self,
        remaining: Tuple[int, ...],
        occupied_mask: int,
    ) -> bool:
        """Check whether every empty cell can still be covered.

        This is a necessary feasibility condition. It does not prove that the
        state is solvable, but it detects dead states early.
        """
        reachable_mask = occupied_mask

        for index in remaining:
            for candidate in self._candidates[index]:
                if candidate.mask & occupied_mask == 0:
                    reachable_mask |= candidate.mask

        return reachable_mask == self._full_mask

    def _order_candidates(
        self,
        candidates: Tuple[_Candidate, ...],
        future_indices: Tuple[int, ...],
        occupied_mask: int,
    ) -> Tuple[_Candidate, ...]:
        """Order candidates by a least-constraining-value score."""
        return tuple(
            sorted(
                candidates,
                key=lambda candidate: self._candidate_score(
                    candidate=candidate,
                    future_indices=future_indices,
                    occupied_mask=occupied_mask,
                ),
            )
        )

    def _candidate_score(
        self,
        candidate: _Candidate,
        future_indices: Tuple[int, ...],
        occupied_mask: int,
    ) -> Tuple[int, int, int, int, int]:
        """Return a lexicographic score for candidate ordering.

        Lower scores are preferred.

        The score prioritizes:

        1. Fewer future clues with zero feasible candidates.
        2. Fewer eliminated future candidates.
        3. More compact rectangles.
        4. Earlier row.
        5. Earlier column.
        """
        next_occupied = occupied_mask | candidate.mask

        zero_domains = 0
        eliminated_candidates = 0

        for index in future_indices:
            feasible_count = 0

            for future_candidate in self._candidates[index]:
                if future_candidate.mask & next_occupied == 0:
                    feasible_count += 1
                else:
                    eliminated_candidates += 1

            if feasible_count == 0:
                zero_domains += 1

        rect = candidate.rect
        compactness = rect.height + rect.width

        return (
            zero_domains,
            eliminated_candidates,
            compactness,
            rect.r0,
            rect.c0,
        )
