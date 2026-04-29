"""
gui.py
======
Tkinter-based interface for Shikaku.

The interface is intentionally minimal:

    * The grid is drawn on a Canvas. Click and drag from one corner of a
      rectangle to the opposite corner to place a player rectangle.
    * Right-click on any rectangle to delete it.
    * The status bar reports the validity of the current attempt.
    * Buttons let the user load puzzles, clear, validate, and request
      that the synthetic solver finish the puzzle.

The GUI is decoupled from the solver: it only invokes
`ShikakuSolver(puzzle).solve()` and renders the resulting placements.
"""

from __future__ import annotations

import os
import random
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional, Tuple

from parser import load_puzzle
from puzzle import Clue, Puzzle, Rectangle, Solution
from solver import ShikakuSolver


# ----------------------------------------------------------------------------
# Visual constants
# ----------------------------------------------------------------------------
CELL_SIZE = 48          # pixels per cell
GRID_PADDING = 20       # blank space around the grid
LINE_COLOR = "#888888"
CLUE_FONT = ("Helvetica", 14, "bold")
RECT_BORDER = "#222222"
SELECT_COLOR = "#1976d2"

# Distinguishable fill palette for placed rectangles.
PALETTE = [
    "#ffe0b2", "#bbdefb", "#c8e6c9", "#f8bbd0", "#d1c4e9",
    "#fff9c4", "#b2dfdb", "#ffccbc", "#dcedc8", "#cfd8dc",
    "#f0f4c3", "#b3e5fc", "#e1bee7", "#c5cae9", "#ffe082",
]


# ----------------------------------------------------------------------------
# Application
# ----------------------------------------------------------------------------
class ShikakuApp:
    """Main application class."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Shikaku - Puzzle Player and Solver")

        # Game state
        self.puzzle: Optional[Puzzle] = None
        self.placements: List[Rectangle] = []   # rectangles drawn by the user
        self.drag_start: Optional[Tuple[int, int]] = None
        self.drag_preview_id: Optional[int] = None

        # Build UI
        self._build_toolbar()
        self._build_canvas()
        self._build_statusbar()

        # Start with a small built-in demo puzzle.
        self.set_puzzle(self._demo_puzzle())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=6)
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(bar, text="Open puzzle...", command=self.cmd_open).pack(side=tk.LEFT)
        ttk.Button(bar, text="Demo", command=lambda: self.set_puzzle(self._demo_puzzle())).pack(side=tk.LEFT, padx=4)
        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(bar, text="Clear", command=self.cmd_clear).pack(side=tk.LEFT)
        ttk.Button(bar, text="Validate", command=self.cmd_validate).pack(side=tk.LEFT, padx=4)
        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(bar, text="Solve (synthetic)", command=self.cmd_solve).pack(side=tk.LEFT)
        ttk.Button(bar, text="Hint", command=self.cmd_hint).pack(side=tk.LEFT, padx=4)

    def _build_canvas(self) -> None:
        self.canvas = tk.Canvas(
            self.root, bg="white",
            highlightthickness=0, width=400, height=400,
        )
        self.canvas.pack(side=tk.TOP, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.canvas.bind("<Button-3>", self._on_right_click)  # delete

    def _build_statusbar(self) -> None:
        self.status_var = tk.StringVar(value="Ready.")
        bar = ttk.Frame(self.root)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(bar, textvariable=self.status_var, anchor="w",
                  padding=6, relief="sunken").pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Puzzle wiring
    # ------------------------------------------------------------------
    def set_puzzle(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.placements.clear()
        # Resize the canvas to fit the grid plus padding.
        w = puzzle.cols * CELL_SIZE + 2 * GRID_PADDING
        h = puzzle.rows * CELL_SIZE + 2 * GRID_PADDING
        self.canvas.config(width=w, height=h)
        self.redraw()
        self._set_status(f"Loaded puzzle ({puzzle.rows} x {puzzle.cols}, "
                         f"{len(puzzle.clues)} clues).")

    @staticmethod
    def _demo_puzzle() -> Puzzle:
        # A small canonical 5x5 example.
        return Puzzle(
            rows=5, cols=5,
            clues=[
                Clue(0, 2, 3), Clue(1, 4, 4),
                Clue(2, 0, 6), Clue(4, 3, 6),
                Clue(4, 4, 6),
            ],
        )

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------
    def _pixel_to_cell(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        if self.puzzle is None:
            return None
        col = (x - GRID_PADDING) // CELL_SIZE
        row = (y - GRID_PADDING) // CELL_SIZE
        if 0 <= row < self.puzzle.rows and 0 <= col < self.puzzle.cols:
            return int(row), int(col)
        return None

    def _cell_to_pixel(self, row: int, col: int) -> Tuple[int, int, int, int]:
        x0 = GRID_PADDING + col * CELL_SIZE
        y0 = GRID_PADDING + row * CELL_SIZE
        return x0, y0, x0 + CELL_SIZE, y0 + CELL_SIZE

    # ------------------------------------------------------------------
    # Mouse handlers
    # ------------------------------------------------------------------
    def _on_left_press(self, event) -> None:
        cell = self._pixel_to_cell(event.x, event.y)
        if cell is None:
            return
        self.drag_start = cell

    def _on_left_drag(self, event) -> None:
        if self.drag_start is None:
            return
        cell = self._pixel_to_cell(event.x, event.y)
        if cell is None:
            return
        if self.drag_preview_id is not None:
            self.canvas.delete(self.drag_preview_id)
        rect = self._normalize_drag(self.drag_start, cell)
        x0, y0, _, _ = self._cell_to_pixel(rect.r0, rect.c0)
        _, _, x1, y1 = self._cell_to_pixel(rect.r1 - 1, rect.c1 - 1)
        self.drag_preview_id = self.canvas.create_rectangle(
            x0, y0, x1, y1, outline=SELECT_COLOR, width=3, dash=(4, 2),
        )

    def _on_left_release(self, event) -> None:
        if self.drag_start is None:
            return
        cell = self._pixel_to_cell(event.x, event.y)
        if cell is not None:
            rect = self._normalize_drag(self.drag_start, cell)
            self._add_player_rectangle(rect)
        self.drag_start = None
        if self.drag_preview_id is not None:
            self.canvas.delete(self.drag_preview_id)
            self.drag_preview_id = None
        self.redraw()

    def _on_right_click(self, event) -> None:
        cell = self._pixel_to_cell(event.x, event.y)
        if cell is None:
            return
        row, col = cell
        for i in range(len(self.placements) - 1, -1, -1):
            if self.placements[i].contains(row, col):
                self.placements.pop(i)
                self.redraw()
                self._set_status("Rectangle removed.")
                return

    @staticmethod
    def _normalize_drag(a: Tuple[int, int], b: Tuple[int, int]) -> Rectangle:
        r0, r1 = sorted([a[0], b[0]])
        c0, c1 = sorted([a[1], b[1]])
        return Rectangle(r0, c0, r1 + 1, c1 + 1)

    def _add_player_rectangle(self, rect: Rectangle) -> None:
        # A user rectangle replaces any existing one that overlaps it.
        self.placements = [
            r for r in self.placements if not r.overlaps(rect)
        ]
        self.placements.append(rect)
        self._set_status(
            f"Placed rectangle ({rect.height} x {rect.width}, area={rect.area})."
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def redraw(self) -> None:
        self.canvas.delete("all")
        if self.puzzle is None:
            return

        # Filled rectangles (player or solver placements).
        for idx, rect in enumerate(self.placements):
            color = PALETTE[idx % len(PALETTE)]
            x0, y0, _, _ = self._cell_to_pixel(rect.r0, rect.c0)
            _, _, x1, y1 = self._cell_to_pixel(rect.r1 - 1, rect.c1 - 1)
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                fill=color, outline=RECT_BORDER, width=2,
            )

        # Grid lines.
        for r in range(self.puzzle.rows + 1):
            y = GRID_PADDING + r * CELL_SIZE
            self.canvas.create_line(
                GRID_PADDING, y,
                GRID_PADDING + self.puzzle.cols * CELL_SIZE, y,
                fill=LINE_COLOR,
            )
        for c in range(self.puzzle.cols + 1):
            x = GRID_PADDING + c * CELL_SIZE
            self.canvas.create_line(
                x, GRID_PADDING,
                x, GRID_PADDING + self.puzzle.rows * CELL_SIZE,
                fill=LINE_COLOR,
            )

        # Clue numbers.
        for clue in self.puzzle.clues:
            x0, y0, x1, y1 = self._cell_to_pixel(clue.row, clue.col)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            # Small white halo so the number is readable on any color.
            self.canvas.create_oval(cx - 16, cy - 16, cx + 16, cy + 16,
                                    fill="white", outline="")
            self.canvas.create_text(cx, cy, text=str(clue.value),
                                    font=CLUE_FONT, fill="black")

    # ------------------------------------------------------------------
    # Toolbar commands
    # ------------------------------------------------------------------
    def cmd_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Shikaku puzzle",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.set_puzzle(load_puzzle(path))
        except Exception as exc:                              # pragma: no cover
            messagebox.showerror("Could not load puzzle", str(exc))

    def cmd_clear(self) -> None:
        self.placements.clear()
        self.redraw()
        self._set_status("Cleared.")

    def cmd_validate(self) -> None:
        if self.puzzle is None or not self.placements:
            self._set_status("Nothing to validate.")
            return
        # Build a Solution if and only if every clue has a matching rectangle.
        clue_to_rect = {}
        unmatched_rects = list(self.placements)
        for clue in self.puzzle.clues:
            found = None
            for r in unmatched_rects:
                if r.contains(clue.row, clue.col) and r.area == clue.value:
                    found = r
                    break
            if found is None:
                self._set_status(
                    "Not yet a valid solution: clue at "
                    f"({clue.row},{clue.col})={clue.value} is not satisfied."
                )
                return
            unmatched_rects.remove(found)
            clue_to_rect[clue] = found

        if unmatched_rects:
            self._set_status("Some rectangles do not contain any clue.")
            return

        sol = Solution(
            self.puzzle,
            [(c, clue_to_rect[c]) for c in self.puzzle.clues],
        )
        if sol.is_valid():
            self._set_status("Correct! The puzzle is solved.")
            messagebox.showinfo("Shikaku", "Correct - puzzle solved!")
        else:
            self._set_status("Almost - rectangles overlap or do not cover the grid.")

    def cmd_solve(self) -> None:
        if self.puzzle is None:
            return
        self._set_status("Solving...")
        self.root.update_idletasks()
        try:
            solver = ShikakuSolver(self.puzzle)
            solution = solver.solve(time_limit=30.0)
        except Exception as exc:                              # pragma: no cover
            messagebox.showerror("Solver error", str(exc))
            return

        if solution is None:
            self._set_status(
                f"No solution found ({solver.stats.nodes_visited} nodes, "
                f"{solver.stats.elapsed_seconds:.3f}s)."
            )
            messagebox.showwarning("Shikaku", "The solver could not find a solution.")
            return

        self.placements = [rect for _, rect in solution.placements]
        self.redraw()
        self._set_status(
            f"Solved in {solver.stats.elapsed_seconds:.3f}s "
            f"({solver.stats.nodes_visited} nodes, "
            f"{solver.stats.backtracks} backtracks)."
        )

    def cmd_hint(self) -> None:
        """Place a single rectangle from the synthetic solver."""
        if self.puzzle is None:
            return
        try:
            solver = ShikakuSolver(self.puzzle)
            solution = solver.solve(time_limit=10.0)
        except Exception as exc:                              # pragma: no cover
            messagebox.showerror("Solver error", str(exc))
            return
        if solution is None:
            self._set_status("No solution available - cannot give a hint.")
            return
        # Pick a clue whose rectangle is not yet correctly placed.
        for clue, correct in solution.placements:
            already = any(
                r == correct
                for r in self.placements
            )
            if not already:
                # Remove any user rectangle that overlaps the hint, then add it.
                self.placements = [
                    r for r in self.placements if not r.overlaps(correct)
                ]
                self.placements.append(correct)
                self.redraw()
                self._set_status(
                    f"Hint: clue ({clue.row},{clue.col})={clue.value} placed."
                )
                return
        self._set_status("All hints already on the board.")

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self.status_var.set(text)


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------
def main() -> None:                                           # pragma: no cover
    root = tk.Tk()
    app = ShikakuApp(root)
    root.mainloop()


if __name__ == "__main__":                                    # pragma: no cover
    main()
