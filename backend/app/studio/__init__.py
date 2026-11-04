"""Studio authoring support.

Phase 0/1 keeps the runtime on code: JSON sentence specs are an authoring
source and a test fixture, not an interpreter input. `sentence_spec` owns the
schema, `export` writes the deterministic files, and `preview` validates and
renders a bounded fixture against the real per-bar realizers.
"""
"""
