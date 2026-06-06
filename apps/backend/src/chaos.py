"""
Central chaos controller (promoted from src/slice/chaos.py for the real graph).

One singleton holds every failure toggle. Nodes/tools consult it; the CLI (or
the demo UI) writes to it. Per CONTEXT.md §A11 chaos triggers must be reliable,
which is why all four toggles live in ONE place.

Toggles wired:
  - fail_tool          : tool failure. `True` fails EVERY tool call (drives the
                         all-tools degradation branch); a tool-NAME string (e.g.
                         "get_room_rent_rule") fails only THAT tool, so the agent
                         can still answer what the other tools verify and
                         drop-and-note only the failed part.
  - fail_tool_once     : attempt 1 raises, attempt 2 succeeds (transient)
  - crash_after_tools  : crash_point hard-kills with os._exit(1)
  - break_model        : routes synthesis to the gateway "break model" virtual
                         (TFY_MODEL_CHAOS) so the Tier-1 fallback chain fires;
                         the resilient-agent virtual model carries the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChaosController:
    # bool True → all tools fail; str → only the named tool fails.
    fail_tool: bool | str = False
    fail_tool_once: bool = False
    _fail_tool_once_consumed: bool = field(default=False, repr=False)

    crash_after_tools: bool = False

    break_model: bool = False

    def reset(self) -> None:
        self.fail_tool = False
        self.fail_tool_once = False
        self._fail_tool_once_consumed = False
        self.crash_after_tools = False
        self.break_model = False

    def _targets(self, tool_name: str) -> bool:
        """Does the armed `fail_tool` setting target this tool?

        `True` targets all tools; a non-empty string targets only the tool whose
        name matches exactly. Anything else (False / "") targets nothing.
        """
        if self.fail_tool is True:
            return True
        if isinstance(self.fail_tool, str) and self.fail_tool:
            return self.fail_tool == tool_name
        return False

    def maybe_fail_tool(self, tool_name: str) -> None:
        """Raise a simulated TimeoutError when armed. Otherwise do nothing.

        `fail_tool_once` flips its own latch here (not in the tool) so tool
        bodies stay dumb.
        """
        if self._targets(tool_name):
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
    fail_tool: bool | str = False,
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
