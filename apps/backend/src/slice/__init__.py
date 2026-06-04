"""
Step-3 vertical slice.

A throwaway-ish 5-node LangGraph whose only purpose is to de-risk two
orchestration-resilience mechanics before the real graph is built:

  1. Tool-failure honest-degradation branch.
  2. Crash-mid-graph + checkpoint resume (real os._exit, real disk-backed
     SQLite checkpointer).

Keep small. See CONTEXT.md §A4, §A10 step 3, §A11.
"""
