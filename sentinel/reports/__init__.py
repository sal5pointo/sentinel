"""Reports: goal math, daily/EOD (later), dashboard."""

from sentinel.reports.goal_math import GoalMathRow, compute_goal_math, render_goal_math_table

__all__ = ["GoalMathRow", "compute_goal_math", "render_goal_math_table"]
