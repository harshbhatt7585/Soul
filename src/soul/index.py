from __future__ import annotations

import sys

# TODO: Parse CLI arguments for mode, model override, and workspace selection.
# TODO: Load runtime configuration from the selected workspace root.
# TODO: Initialize the concrete agent implementation once the public agent API is finalized.
# TODO: Route interactive sessions through the REPL and add support for one-shot command execution.
# TODO: Return stable exit codes for configuration, runtime, and user-interrupt failures.


def main() -> int:
    """Temporary CLI entrypoint until the runtime wiring is implemented."""
    # TODO: Replace this placeholder with the actual CLI bootstrap flow.
    print("soul.index.main is not implemented yet.", file=sys.stderr)
    return 1
