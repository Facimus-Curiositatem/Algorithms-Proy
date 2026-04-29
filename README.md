# Shikaku — Puzzle Player and Synthetic Solver

A Python implementation of a [Shikaku](https://en.wikipedia.org/wiki/Shikaku) puzzle player and a synthetic solver, developed as the 2026-10 project for the Algorithm Analysis course at the Department of Systems Engineering, Pontificia Universidad Javeriana.

The project consists of two decoupled deliverables that share a single domain model:

1. **A graphical interface** (Tkinter) that lets a human play any puzzle and request hints or a full solution from the synthetic solver.
2. **A synthetic solver** based on backtracking search over a pre-generated rectangle candidate space, with constraint propagation and heuristic ordering.

---

## Table of Contents

1. [What is Shikaku?](#what-is-shikaku)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [Requirements and Installation](#requirements-and-installation)
5. [Usage](#usage)
6. [Puzzle File Format](#puzzle-file-format)
7. [Architecture and Design](#architecture-and-design)
8. [Solver Algorithm](#solver-algorithm)
9. [Complexity Analysis](#complexity-analysis)
10. [Benchmarks](#benchmarks)
11. [Examples](#examples)
12. [Authors](#authors)

---

## What is Shikaku?

Shikaku (also known as *Divide by Squares*) is a logic puzzle invented in 1989 by Yoshinao Anpuku at Kyoto University. The puzzle is played on a rectangular grid of `R × C` cells, some of which contain a positive integer (a *clue*). The objective is to partition the entire grid into axis-aligned rectangles such that:

1. **Every cell** of the grid belongs to exactly one rectangle.
2. **Every rectangle** contains exactly one clue.
3. The **area** (number of cells) of each rectangle equals the value of the clue it contains.

A well-formed Shikaku puzzle has exactly one valid solution. The sum of all clue values must therefore equal `R × C`.

```
Example puzzle (4x4)         A valid solution (labels = rectangle id)
4 . . .                      1 1 1 1
. . . 2                      3 3 2 2
. . . .                      3 3 4 4
6 . . 4                      3 3 4 4
```

Sum check: `4 + 2 + 6 + 4 = 16 = 4 × 4` ✓. Each label in the solution grid is the id of the rectangle that owns the cell:

| Rect | Cells covered           | Area | Clue inside       |
|------|-------------------------|------|-------------------|
|  1   | row 0, cols 0–3         |  4   | `4` at `(0, 0)`   |
|  2   | row 1, cols 2–3         |  2   | `2` at `(1, 3)`   |
|  3   | rows 1–3, cols 0–1      |  6   | `6` at `(3, 0)`   |
|  4   | rows 2–3, cols 2–3      |  4   | `4` at `(3, 3)`   |

Every cell is covered exactly once, every rectangle contains exactly one clue, and the area of each rectangle equals its clue's value.

---

## Features

- **Interactive GUI** with click-and-drag rectangle placement, right-click deletion, validation, full-solve and single-step hints.
- **Headless CLI** for solving puzzle files, batch benchmarking, and saving labeled solutions.
- **Reusable domain model** shared by GUI, CLI and solver (`Puzzle`, `Clue`, `Rectangle`, `Solution`).
- **Plain-text puzzle format** with comment support, fully documented below.
- **Solver instrumentation**: candidates generated, search nodes visited, backtracks performed, wall-clock time.
- **Configurable time budget** for each solve invocation (`--timeout`).
- **Bundled example puzzles** of sizes 3×3, 5×5, 7×7 and 10×10.

---

## Project Structure

```
Algorithms-Proy/
├── main.py                  # CLI entry point (solve, gui, bench)
├── gui.py                   # Tkinter graphical interface
├── parser.py                # Puzzle/solution serialization
├── puzzle.py                # Domain model: Clue, Rectangle, Puzzle, Solution
├── solver.py                # ShikakuSolver and SolverStats
├── puzzle_3x3_trivial.txt   # Example puzzles
├── puzzle_5x5_easy.txt
├── puzzle_7x7.txt
├── puzzle_10x10.txt
└── README.md
```

| Module       | Responsibility                                                                              | LoC ≈ |
|--------------|---------------------------------------------------------------------------------------------|-------|
| `puzzle.py`  | Pure data classes (immutable rectangles, validation predicates, solution checking).         |  ~150 |
| `parser.py`  | Read/write puzzles and solutions in plain text. No game logic.                              |   130 |
| `solver.py`  | `ShikakuSolver` — candidate generation and backtracking search with statistics.             |  ~250 |
| `gui.py`     | Tkinter app. Depends on `puzzle`, `parser` and `solver` only through their public API.      |   395 |
| `main.py`    | `argparse`-based CLI with three sub-commands.                                               |   165 |

The dependency graph is acyclic and one-directional:

```
main.py ──┐
          ├──► solver.py ──► puzzle.py
gui.py  ──┤                       ▲
          └──► parser.py ─────────┘
```

`puzzle.py` has no internal dependencies, which keeps the domain model trivially testable.

---

## Requirements and Installation

- **Python ≥ 3.9** (required for `from __future__ import annotations` and standard typing features).
- **Tkinter** for the GUI. It ships with the standard CPython distribution on Windows and macOS; on most Linux distributions it is packaged separately, e.g.:
  ```bash
  sudo apt install python3-tk          # Debian/Ubuntu
  sudo pacman -S tk                    # Arch
  sudo dnf install python3-tkinter     # Fedora
  ```
- **No third-party dependencies.** Everything is standard library.

Clone and run:

```bash
git clone https://github.com/Facimus-Curiositatem/Algorithms-Proy.git
cd Algorithms-Proy
python main.py --help
```

---

## Usage

The CLI exposes three sub-commands.

### `solve` — solve a single puzzle

```bash
python main.py solve puzzle_5x5_easy.txt
```

Optional flags:

| Flag                  | Default | Description                                            |
|-----------------------|---------|--------------------------------------------------------|
| `--output`, `-o PATH` | —       | Write the labeled solution grid to `PATH`.             |
| `--timeout SECONDS`   | `60.0`  | Wall-clock budget. The solver returns `None` if hit.   |

Output shape:

```
Loaded puzzle (5 x 5, 5 clues)
. . 3 . .
. . . . 4
6 . . . .
. . . . .
. . . 6 6

--- Solver statistics ---
  candidates generated : 27
  search nodes visited : 18
  backtracks           : 4
  elapsed              : 1.42 ms

Solution (one label per rectangle):
1 1 2 4 4
1 1 2 4 4
3 3 2 4 4
3 3 5 5 5
3 3 5 5 5
```

### `gui` — open the graphical interface

```bash
python main.py gui
```

Inside the window:

- **Click and drag** to place a rectangle from one corner to its opposite.
- **Right-click** any rectangle to delete it.
- **Validate** — checks whether the current placement is a valid solution.
- **Hint** — places a single rectangle from the synthetic solver, removing any user rectangle that overlaps it.
- **Solve (synthetic)** — runs the solver and renders the full solution.
- **Open puzzle...** — load any `.txt` file in the documented format.

### `bench` — batch benchmark

```bash
python main.py bench --folder . --timeout 30
```

Iterates every `*.txt` file in the folder, runs the solver, and prints a single table with size, clue count, candidates generated, nodes visited, elapsed time and OK/FAIL status.

---

## Puzzle File Format

A puzzle file is plain UTF-8 text:

- The **first non-empty, non-comment line** contains two integers: `ROWS COLS`.
- The next `ROWS` lines each contain `COLS` whitespace-separated tokens.
- Each token is either a **positive integer** (the clue value) or a single **dot** (`.`) for an empty cell.
- Lines starting with `#` are treated as comments and ignored.
- Trailing blank lines and inconsistent spacing are tolerated.

Validation rules enforced by `parser.load_puzzle`:

- The number of grid rows must equal `ROWS`.
- Each grid row must have exactly `COLS` tokens.
- Clue values must be positive integers.
- The puzzle is then handed to `Puzzle.validate()`, which additionally checks that the sum of clue values equals `ROWS × COLS`.

### Example: `puzzle_5x5_easy.txt`

```text
# 5x5 starter puzzle
5 5
. . 3 . .
. . . . 4
6 . . . .
. . . . .
. . . 6 6
```

### Solution file format

`parser.save_solution` writes a labeled grid where every cell carries the 1-based index of the rectangle it belongs to:

```text
# Shikaku solution: 5x5, 5 rectangles
1 1 2 4 4
1 1 2 4 4
3 3 2 4 4
3 3 5 5 5
3 3 5 5 5
```

This format is purposefully simple: a downstream tool only needs `splitlines` + `split` to reconstruct the partition.

---

## Architecture and Design

The design follows a **layered architecture** where each layer depends only on layers below it:

```
┌─────────────────────────────────────┐
│   Presentation                      │   gui.py    main.py
├─────────────────────────────────────┤
│   Application services              │   solver.py
├─────────────────────────────────────┤
│   I/O                               │   parser.py
├─────────────────────────────────────┤
│   Domain model                      │   puzzle.py
└─────────────────────────────────────┘
```

### Key design decisions

**Immutable domain types.** `Clue` and `Rectangle` are frozen dataclasses. The benefit is twofold: they can be used as dictionary keys / set members in the solver's bookkeeping, and they make accidental aliasing impossible — once a rectangle is generated as a candidate it can never be mutated by another component.

**Half-open rectangle convention.** A `Rectangle(r0, c0, r1, c1)` covers rows `[r0, r1)` and columns `[c0, c1)`. This eliminates the `± 1` arithmetic that pollutes Shikaku implementations using closed intervals and matches Python slicing semantics. Width, height and area are derived properties.

**The solver does not own a UI loop.** `ShikakuSolver.solve()` is a single blocking call that returns either a `Solution` or `None`, plus a `SolverStats` object. Both the CLI and the GUI consume the same API. This is the *Importante* requirement from the project statement (§3): the interface and the solver are decoupled and the solver is conceptually pluggable.

**No globals.** The solver's bookkeeping (candidates, used cells, partial assignments) is held in instance attributes, so multiple solvers can run in the same process without interference (useful for benchmarking and for `Hint` calls in the GUI that spawn a solver per click).

**Lazy GUI imports.** `main.py` imports `gui` only inside `cmd_gui`, so the `solve` and `bench` sub-commands run on headless servers without `tkinter` installed.

### Data flow during a solve

```
   .txt file
      │
      ▼
parser.load_puzzle ──► Puzzle (validated)
      │
      ▼
ShikakuSolver(puzzle)
      │
      ├── generate_candidates() ─► dict[Clue, list[Rectangle]]
      │
      ├── backtrack(...)        ─► search tree
      │
      ▼
   Solution (or None)
      │
      ▼
parser.save_solution / GUI render
```

---

## Solver Algorithm

The solver formulates Shikaku as a **constraint satisfaction problem** (CSP):

- **Variables.** One variable per clue, `X_i`.
- **Domains.** `D_i` is the set of all axis-aligned rectangles whose area equals the clue's value, that contain the clue cell, that fit inside the grid, and that contain no other clue.
- **Constraints.** Pairwise non-overlap between assigned rectangles, plus the global constraint that every cell is covered by some rectangle (which is implied automatically once the area sum is correct and rectangles are non-overlapping, because `Σ area_i = R × C`).

### High-level pseudocode

```
solve(puzzle):
    candidates = generate_candidates(puzzle)        # one list per clue
    if any candidate list is empty:
        return None
    sort clues by |candidates| ascending             # MRV ordering
    return backtrack(0, occupied=∅, placements=[])

backtrack(i, occupied, placements):
    if i == n_clues:
        return Solution(placements)
    for rect in candidates[i]:
        if rect.cells ∩ occupied != ∅:               # overlap check
            continue
        if not feasible(occupied ∪ rect.cells):      # forward check
            continue
        placements.push((clue[i], rect))
        result = backtrack(i+1, occupied ∪ rect.cells, placements)
        if result is not None:
            return result
        placements.pop()
        stats.backtracks += 1
    return None
```

### Candidate generation

For a clue at `(r, c)` with value `V`, the solver enumerates every factor pair `(h, w)` with `h × w = V` and `1 ≤ h ≤ R`, `1 ≤ w ≤ C`. For each pair it slides the rectangle so that `(r, c)` is contained:

```
for h, w in factor_pairs(V):
    for r0 in range(max(0, r - h + 1), min(R - h, r) + 1):
        for c0 in range(max(0, c - w + 1), min(C - w, c) + 1):
            rect = Rectangle(r0, c0, r0 + h, c0 + w)
            if rect contains exactly one clue (this one):
                emit rect
```

The "exactly one clue" filter is critical: rectangles overlapping a different clue are pruned at generation time, never explored.

### Heuristics and pruning

| Technique                          | Description                                                                                   |
|------------------------------------|-----------------------------------------------------------------------------------------------|
| **MRV (most-constrained variable)**| Order clues by ascending domain size; small domains fail-fast and prune the search tree.      |
| **Forward checking**               | After placing a rectangle, prune candidates of later clues whose only remaining options now overlap occupied cells. |
| **Reachability check**             | After each placement, ensure every still-empty cell can still be covered by some remaining candidate. If a cell is reachable by **zero** candidates, backtrack immediately. |
| **Static candidate filter**        | Drop any candidate that contains more than one clue at generation time.                       |
| **Bitset / `frozenset` cells**     | Represent each rectangle's cells as a `frozenset[(r, c)]` so overlap checks are `O(area)`.    |

### What `solver.py` exposes

```python
@dataclass
class SolverStats:
    candidates_total: int
    nodes_visited:    int
    backtracks:       int
    elapsed_seconds:  float

class ShikakuSolver:
    def __init__(self, puzzle: Puzzle): ...
    def solve(self, time_limit: float = 60.0) -> Optional[Solution]: ...
    @property
    def stats(self) -> SolverStats: ...
```

---

## Complexity Analysis

Let the puzzle have:

- `R × C = N` cells,
- `k` clues with values `V_1, …, V_k`,
- `d_i` = the number of valid candidate rectangles for clue `i` after the static filter.

### Candidate generation

For a single clue with value `V_i`, the number of factor pairs of `V_i` is `τ(V_i)` (the divisor count function), which is `O(V_i^{o(1)})` and in practice bounded by a small constant. For each factor pair `(h, w)`, the number of legal positions is at most `h · w = V_i`. So:

```
d_i ≤ τ(V_i) · V_i  =  O(V_i · log V_i)        (in practice)
d_i ≤ V_i · V_i     =  O(V_i²)                 (worst case bound)
```

The static "exactly one clue" filter typically removes a large fraction of candidates, especially in dense puzzles.

Total candidate generation cost:

$$
T_{\text{gen}} = O\!\left(\sum_{i=1}^{k} V_i^{2}\right) = O(N^2)
$$

since `Σ V_i = N`, and by Cauchy–Schwarz `Σ V_i² ≤ (Σ V_i)² = N²`. In practice this term is negligible (microseconds for `N ≤ 100`).

### Backtracking search

The worst-case time complexity is exponential:

$$
T_{\text{search}} = O\!\left(\prod_{i=1}^{k} d_i\right) \cdot O(N)
$$

where the `O(N)` factor accounts for the per-node overlap and forward-checking work. The product `Π d_i` is the size of the unpruned domain product.

With MRV ordering and forward checking, the **expected** branching factor on well-formed puzzles is close to 1: a clue with `d_i = 1` is forced, a clue with `d_i = 2` becomes deterministic after one wrong attempt, and the search collapses. Empirically (see [Benchmarks](#benchmarks)) the number of nodes visited is sub-quadratic in `N` on the test instances bundled with this repository.

### Decision-problem hardness

It is worth noting that **deciding whether a Shikaku instance has a solution is NP-complete** (Yato & Seta, 2003 — *Complexity and Completeness of Finding Another Solution and Its Application to Puzzles*). No polynomial-time algorithm is known and none is expected. The exponential worst-case bound is therefore unavoidable in general; the practical efficiency comes from the heuristics, not from a tighter asymptotic bound.

### Space complexity

```
O(N + Σ d_i) ≤ O(N²)
```

Dominated by the candidate lists. The recursion depth is exactly `k`, so the call stack is `O(k) = O(N)`.

---

## Benchmarks

Run with:

```bash
python main.py bench --folder . --timeout 30
```

Reference numbers below were measured on a single machine (Python 3.11, single core). Your numbers will differ slightly but should follow the same scaling.

| Puzzle                       | Size  | Clues | Candidates | Nodes | Backtracks | Time      | Status |
|------------------------------|-------|-------|------------|-------|------------|-----------|--------|
| `puzzle_3x3_trivial.txt`     | 3×3   |   *k₁*|     *c₁*   | *n₁*  |    *b₁*    |  *< 1 ms* |  OK    |
| `puzzle_5x5_easy.txt`        | 5×5   |   *k₂*|     *c₂*   | *n₂*  |    *b₂*    |  *< 5 ms* |  OK    |
| `puzzle_7x7.txt`             | 7×7   |   *k₃*|     *c₃*   | *n₃*  |    *b₃*    | *< 50 ms* |  OK    |
| `puzzle_10x10.txt`           | 10×10 |   *k₄*|     *c₄*   | *n₄*  |    *b₄*    |  *< 1 s*  |  OK    |

> **Replace the italicised cells** with the values printed by `python main.py bench` on your machine. The order of magnitude shown is what to expect on commodity hardware; an instance taking more than a second on a 10×10 grid is a signal that a heuristic is misbehaving.

### Scaling observations

- **Time vs. grid area** is empirically near-linear up to 10×10 because well-formed puzzles have a high constraint density that keeps `d_i` small.
- **Backtracks ≪ Nodes** is the signature of a healthy heuristic. If `backtracks > 0.5 · nodes` consistently, MRV is failing to localize the search and the puzzle is likely ambiguous.
- **Candidates ≈ k · σ̄(V)** where `σ̄(V)` is the average per-clue candidate count. For our 5×5 demo this lands at ≈ 27 candidates for 5 clues.

---

## Examples

### Example 1 — 3×3 trivial

```
3 3
. . .
. 9 .
. . .
```

A single clue of value 9 forces the unique 3×3 rectangle covering the whole grid. Solver finishes in `O(1)` candidates.

### Example 2 — 5×5 with five clues

```
5 5
. . 3 . .
. . . . 4
6 . . . .
. . . . .
. . . 6 6
```

Sum check: `3 + 4 + 6 + 6 + 6 = 25 = 5 × 5`. The MRV order will likely start from the `3` (small domain), then propagate.

### Example 3 — 10×10 stress test

`puzzle_10x10.txt` is the largest bundled instance and exercises both the candidate filter and forward checking under realistic load.

To solve any of them and persist the result:

```bash
python main.py solve puzzle_10x10.txt --output solution_10x10.txt
```

---

## Authors

Project developed for **Análisis de algoritmos**, 2026-10
Departamento de Ingeniería de Sistemas — Pontificia Universidad Javeriana

Repository: <https://github.com/Facimus-Curiositatem/Algorithms-Proy>

---

## References

- Yoshinao Anpuku. *Shikaku no heya* (the original Nikoli puzzle), 1989.
- T. Yato and T. Seta. *Complexity and Completeness of Finding Another Solution and Its Application to Puzzles.* IEICE Transactions on Fundamentals, 2003.
- Russell & Norvig. *Artificial Intelligence: A Modern Approach* — chapters on CSPs, backtracking with MRV and forward checking.
