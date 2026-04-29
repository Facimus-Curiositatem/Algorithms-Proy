"""
main.py
=======
Command-line entry point for the Shikaku project.

Examples
--------
Solve a puzzle from a file and print the solution::

    python main.py solve examples/puzzle_5x5.txt

Save the solution to a file::

    python main.py solve examples/puzzle_5x5.txt --output solution.txt

Launch the graphical interface::

    python main.py gui

Run the built-in benchmark on bundled examples::

    python main.py bench
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import List

from parser import load_puzzle, save_solution
from puzzle import Solution
from solver import ShikakuSolver


# ----------------------------------------------------------------------------
# Pretty printing
# ----------------------------------------------------------------------------
def _render_solution(solution: Solution) -> str:
    rows, cols = solution.puzzle.rows, solution.puzzle.cols
    labels = [[0] * cols for _ in range(rows)]
    for idx, (_, rect) in enumerate(solution.placements, start=1):
        for r, c in rect.cells():
            labels[r][c] = idx
    cell_w = len(str(len(solution.placements)))
    return "\n".join(
        " ".join(str(v).rjust(cell_w) for v in row) for row in labels
    )


# ----------------------------------------------------------------------------
# Sub-commands
# ----------------------------------------------------------------------------
def cmd_solve(args: argparse.Namespace) -> int:
    puzzle = load_puzzle(args.puzzle)
    print(f"Loaded puzzle ({puzzle.rows} x {puzzle.cols}, "
          f"{len(puzzle.clues)} clues)")
    print(puzzle)
    print()

    solver = ShikakuSolver(puzzle)
    solution = solver.solve(time_limit=args.timeout)

    print("--- Solver statistics ---")
    print(f"  candidates generated : {solver.stats.candidates_total}")
    print(f"  search nodes visited : {solver.stats.nodes_visited}")
    print(f"  backtracks           : {solver.stats.backtracks}")
    print(f"  elapsed              : {solver.stats.elapsed_seconds*1000:.2f} ms")
    print()

    if solution is None:
        print("No solution found.")
        return 1

    print("Solution (one label per rectangle):")
    print(_render_solution(solution))

    if args.output:
        save_solution(solution, args.output)
        print(f"\nWritten to {args.output}")
    return 0


def cmd_gui(_args: argparse.Namespace) -> int:                # pragma: no cover
    # Imported lazily so the CLI works on systems without tkinter.
    from gui import main as gui_main
    gui_main()
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    folder = args.folder
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a directory.", file=sys.stderr)
        return 2

    puzzles: List[str] = sorted(
        os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".txt")
    )
    if not puzzles:
        print(f"No .txt puzzles found in {folder}", file=sys.stderr)
        return 2

    print(f"{'puzzle':<32} {'size':>8} {'clues':>6} "
          f"{'cands':>7} {'nodes':>7} {'time(ms)':>9}  status")
    print("-" * 80)
    for path in puzzles:
        try:
            puzzle = load_puzzle(path)
        except Exception as exc:
            print(f"{os.path.basename(path):<32}  load error: {exc}")
            continue

        solver = ShikakuSolver(puzzle)
        solution = solver.solve(time_limit=args.timeout)
        size = f"{puzzle.rows}x{puzzle.cols}"
        status = "OK" if solution and solution.is_valid() else "FAIL"
        print(f"{os.path.basename(path):<32} {size:>8} "
              f"{len(puzzle.clues):>6} "
              f"{solver.stats.candidates_total:>7} "
              f"{solver.stats.nodes_visited:>7} "
              f"{solver.stats.elapsed_seconds*1000:>9.2f}  {status}")
    return 0


# ----------------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shikaku",
        description="Shikaku puzzle player and synthetic solver.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_solve = sub.add_parser("solve", help="Solve a puzzle from a file.")
    p_solve.add_argument("puzzle", help="Path to a puzzle file.")
    p_solve.add_argument("--output", "-o", help="Where to save the solution.")
    p_solve.add_argument("--timeout", type=float, default=60.0,
                         help="Wall-clock time budget in seconds (default: 60).")
    p_solve.set_defaults(func=cmd_solve)

    p_gui = sub.add_parser("gui", help="Launch the graphical interface.")
    p_gui.set_defaults(func=cmd_gui)

    p_bench = sub.add_parser("bench", help="Benchmark every puzzle in a folder.")
    p_bench.add_argument("--folder", "-f", default="examples",
                         help="Folder containing .txt puzzles (default: examples).")
    p_bench.add_argument("--timeout", type=float, default=30.0,
                         help="Per-puzzle time limit in seconds.")
    p_bench.set_defaults(func=cmd_bench)

    return parser


def main(argv: List[str] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":                                    # pragma: no cover
    sys.exit(main())
