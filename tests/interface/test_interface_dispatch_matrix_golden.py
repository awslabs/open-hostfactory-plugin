"""Golden snapshot of the current interface x operation dispatch/format matrix.

This locks the present state of how each logical operation reaches its work
(``dispatch``) and how its response is rendered (``format``) on each interface.
Its purpose is to make later convergence work provable: when an operation is
migrated onto the orchestrator-and-formatter path, the corresponding cell here
changes in the same commit, so a diff shows the improvement and an accidental
regression cannot slip through silently.

Dispatch/format vocabulary (mirrors the recorded analysis):
    orch  — routes through a per-operation orchestrator
    bus   — QueryBus/CommandBus dispatched directly
    svc   — a service invoked directly
    RFS   — rendered through ResponseFormattingService
    sched — rendered via SchedulerPort.format_* directly
    inline— response hand-built in the adapter
    —     — operation absent on that interface

Each cell is ``"<dispatch>/<format>"`` or ``None`` when the operation is not
exposed on that interface.
"""

import json
from pathlib import Path

CURRENT_MATRIX: dict[str, dict[str, str | None]] = {
    "request_machines": {
        "cli": "orch/RFS",
        "rest": "orch/RFS",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "return_machines": {
        "cli": "orch/RFS",
        "rest": "orch/RFS",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "get_request_status": {
        "cli": "orch/RFS",
        "rest": "orch/RFS",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "list_requests": {
        "cli": "orch/RFS",
        "rest": "orch/RFS",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "list_return_requests": {
        "cli": "orch/RFS",
        "rest": "orch/RFS",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "cancel_request": {
        "cli": "orch/RFS",
        "rest": "orch/RFS",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "watch_request_status": {
        "cli": "orch/inline",
        "rest": "orch/RFS",
        "mcp": None,
        "sdk": None,
    },
    "list_machines": {
        "cli": "orch/RFS",
        "rest": "orch/RFS",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "get_machine": {
        "cli": "orch/RFS",
        "rest": "orch/RFS",
        "mcp": None,
        "sdk": "orch/sched",
    },
    "sync_machine": {
        "cli": None,
        "rest": "orch/RFS",
        "mcp": None,
        "sdk": None,
    },
    "stop_machines": {
        "cli": "orch/RFS",
        "rest": None,
        "mcp": "orch/RFS",
        "sdk": "bus/sched",
    },
    "start_machines": {
        "cli": "orch/RFS",
        "rest": None,
        "mcp": "orch/RFS",
        "sdk": "bus/sched",
    },
    "list_templates": {
        "cli": "orch/RFS",
        "rest": "orch/sched",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "get_template": {
        "cli": "orch/RFS",
        "rest": "orch/sched",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "create_template": {
        "cli": "orch/RFS",
        "rest": "orch/sched",
        "mcp": None,
        "sdk": "orch/sched",
    },
    "update_template": {
        "cli": "orch/RFS",
        "rest": "orch/sched",
        "mcp": None,
        "sdk": "orch/sched",
    },
    "delete_template": {
        "cli": "orch/RFS",
        "rest": "orch/sched",
        "mcp": None,
        "sdk": "orch/sched",
    },
    "validate_template": {
        "cli": "orch/RFS",
        "rest": "orch/sched",
        "mcp": "orch/RFS",
        "sdk": "orch/sched",
    },
    "refresh_templates": {
        "cli": "orch/RFS",
        "rest": "orch/sched",
        "mcp": None,
        "sdk": "orch/sched",
    },
}

_GOLDEN_PATH = Path(__file__).with_name("interface_dispatch_matrix_golden.json")

_INTERFACES = ("cli", "rest", "mcp", "sdk")


def test_matrix_is_well_formed() -> None:
    """Every operation declares a cell for every interface."""
    for operation, cells in CURRENT_MATRIX.items():
        assert set(cells) == set(_INTERFACES), operation


def test_matrix_matches_golden() -> None:
    """The recorded matrix matches the committed golden snapshot.

    Regenerate the snapshot deliberately (delete the file and re-run) only when
    an operation's dispatch or format path is intentionally changed.
    """
    serialised = json.dumps(CURRENT_MATRIX, indent=2, sort_keys=True) + "\n"

    if not _GOLDEN_PATH.exists():
        _GOLDEN_PATH.write_text(serialised)

    assert _GOLDEN_PATH.read_text() == serialised
