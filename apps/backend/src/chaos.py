"""
Central chaos controller (promoted from src/slice/chaos.py for the real graph).

One singleton holds every failure toggle. Nodes/tools consult it; the CLI (or
the demo UI) writes to it. Per CONTEXT.md §A11 chaos triggers must be reliable,
which is why all four toggles live in ONE place.

Toggles wired:
  - fail_tool          : every tool call raises (drives the degradation branch)
  - fail_tool_once     : attempt 1 raises, attempt 2 succeeds (transient)
  - crash_after_tools  : crash_point hard-kills with os._exit(1)
  - break_model        : reserved for Step 5 (gateway "break model" virtual);
                         the Tier-1 fallback chain is already live via the
                         resilient-agent virtual model.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChaosController:
    fail_tool: bool = False
    fail_tool_once: bool = False
    _fail_tool_once_consumed: bool = field(default=False, repr=False)

    crash_after_tools: bool = False

    break_model: bool = False  # stubbed for Step 5

    def reset(self) -> None:
        self.fail_tool = False
        self.fail_tool_once = False
        self._fail_tool_once_consumed = False
        self.crash_after_tools = False
        self.break_model = False

    def maybe_fail_tool(self, tool_name: str) -> None:
        """Raise a simulated TimeoutError when armed. Otherwise do nothing.

        `fail_tool_once` flips its own latch here (not in the tool) so tool
        bodies stay dumb.
        """
        if self.fail_tool:
            raise TimeoutError(
                f"[chaos] {tool_name} simulated TimeoutError (fail_tool)"
            )

        if self.fail_tool_once and not self._fail_tool_once_consumed:
            self._fail_tool_once_consumed = True
            raise TimeoutError(
                f"[chaos] {tool_name} simulated TimeoutError (fail_tool_once)"
            )


CHAOS = ChaosController()


def configure(
    *,
    fail_tool: bool = False,
    fail_tool_once: bool = False,
    crash_after_tools: bool = False,
    break_model: bool = False,
) -> None:
    """Replace controller state in one shot. CLI calls this BEFORE building
    the graph so first-attempt nodes see the toggles."""
    CHAOS.reset()
    CHAOS.fail_tool = fail_tool
    CHAOS.fail_tool_once = fail_tool_once
    CHAOS.crash_after_tools = crash_after_tools
    CHAOS.break_model = break_model
