"""
Central chaos controller.

One singleton holds every failure toggle. Nodes/tools consult it; the CLI
(or, later, the demo UI) writes to it. Keeping all the chaos state in ONE
place is per CONTEXT.md §A11 — chaos triggers must be reliable.

Four toggles are wired even though the slice only exercises two, so step 4's
gateway scene plugs straight in without reshaping this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChaosController:
    # --- Tool-layer chaos ---
    # Hard fail: every attempt of the tool raises.
    fail_tool: bool = False
    # Transient: attempt 1 raises, attempt 2 succeeds. After the first arm-and-
    # fire we flip the internal flag so the retry sees a healthy world.
    fail_tool_once: bool = False
    _fail_tool_once_consumed: bool = field(default=False, repr=False)

    # --- Process-layer chaos ---
    # If armed, crash_point calls os._exit(1). Drives the resume scene.
    crash_after_tools: bool = False

    # --- Model-layer chaos (STUB — wired for step 4's gateway scene) ---
    # Not consumed in the slice; included so the controller's shape is stable.
    break_model: bool = False

    def reset(self) -> None:
        self.fail_tool = False
        self.fail_tool_once = False
        self._fail_tool_once_consumed = False
        self.crash_after_tools = False
        self.break_model = False

    # ---- Helpers that nodes/tools call ----

    def maybe_fail_tool(self, tool_name: str) -> str | None:
        """
        Decide whether `tool_name` should fail right now. Returns a resilience-
        event string when it raises (so the caller can log the SAME message it
        appends to state). Raises a simulated TimeoutError when armed.

        - fail_tool: every call raises.
        - fail_tool_once: the first call raises, the next call passes. The flip
          happens here, not in the tool, so the tool itself stays dumb.
        """
        if self.fail_tool:
            msg = f"[chaos] {tool_name} simulated TimeoutError (fail_tool)"
            raise TimeoutError(msg)

        if self.fail_tool_once and not self._fail_tool_once_consumed:
            self._fail_tool_once_consumed = True
            msg = f"[chaos] {tool_name} simulated TimeoutError (fail_tool_once)"
            raise TimeoutError(msg)

        return None


# Module-level singleton. Mutate via the helpers below or directly; the CLI
# sets flags BEFORE building the graph so first-attempt nodes see them.
CHAOS = ChaosController()


def configure(
    *,
    fail_tool: bool = False,
    fail_tool_once: bool = False,
    crash_after_tools: bool = False,
    break_model: bool = False,
) -> None:
    """Replace the controller's state in one shot. Used by the CLI."""
    CHAOS.reset()
    CHAOS.fail_tool = fail_tool
    CHAOS.fail_tool_once = fail_tool_once
    CHAOS.crash_after_tools = crash_after_tools
    CHAOS.break_model = break_model
