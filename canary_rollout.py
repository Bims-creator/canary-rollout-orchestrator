"""
Canary Rollout Orchestrator — DevOps Engineer Assessment (Anzibloom)

See README.md and fake_fleet_spec.md for the full requirements.

Design decisions:
  - MAX_PROMOTION_ATTEMPTS = 20: with ~83% healthy-per-check odds, 3
    consecutive passes is expected within a handful of attempts; 20 gives
    ample margin while still bounding retries on a genuinely broken server
    (srv-4 never becomes healthy, so it always exhausts the cap).
  - On promotion failure, already-promoted servers are rolled back but the
    rollout continues deploying to later servers in the queue (rather than
    aborting entirely), so we still get full information about the rest of
    the fleet.
  - The post-promotion watch phase requires 3 CONSECUTIVE unhealthy checks
    (not just 1) before declaring a regression and triggering a fleet-wide
    rollback. Testing showed a 2-consecutive-fail threshold produced false
    positives from ordinary transient flakiness over a 10-check watch
    window; 3-in-a-row matches the promotion threshold and still reliably
    catches srv-6's regression, since that failure is permanent once it
    starts.
"""

import random
import time
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Fake fleet health-check API (implemented verbatim per fake_fleet_spec.md —
# this part is given, not part of what's being evaluated)
# ---------------------------------------------------------------------------

FLEET = ["srv-1", "srv-2", "srv-3", "srv-4", "srv-5", "srv-6"]


def check_health(server_id: str, check_number: int) -> bool:
    """Returns whether `server_id` is healthy on this check.

    check_number is a per-server monotonically increasing counter, starting
    at 1 for the first-ever check of that server and incrementing by 1 each
    time you check it again — including checks during the post-promotion
    watch phase. You (the caller) own tracking and incrementing it.
    """
    if server_id == "srv-4":
        return False
    if server_id == "srv-6" and check_number >= 7:
        return False
    return random.random() > (1 / 6)


# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

class ServerStatus(Enum):
    PENDING = "pending"
    LIVE = "live"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"          # never stabilized during promotion


@dataclass
class ServerState:
    server_id: str
    status: ServerStatus = ServerStatus.PENDING
    check_number: int = 0      # last check_number used for this server
    reason: str = ""           # human-readable note for the final report


# ---------------------------------------------------------------------------
# Orchestrator — this is the part you need to implement yourself
# ---------------------------------------------------------------------------

# TODO: pick and document a retry cap for the promotion loop. srv-4 is
# always unhealthy, so without a cap this loops forever.
MAX_PROMOTION_ATTEMPTS = 20
WATCH_MAX_CHECKS = 10


def promote_server(state: ServerState) -> bool:
    """
    Attempt to get `state.server_id` to 3 CONSECUTIVE healthy checks.

    Must satisfy:
      - Call check_health(state.server_id, check_number), incrementing
        state.check_number on every call (it persists across the server's
        whole lifetime, including later watch-phase checks).
      - A single unhealthy check does NOT mean abort — it resets your
        consecutive-healthy counter, and you keep trying (up to the cap).
      - A short simulated delay between checks (time.sleep with a small
        value) is required by the README.
      - Stop and return True as soon as you've seen 3 consecutive healthy
        checks.
      - Stop and return False if you hit MAX_PROMOTION_ATTEMPTS without
        getting there — set state.status = ServerStatus.FAILED and fill in
        state.reason.

    Returns True if the server should be promoted, False otherwise.
    """
    consecutive = 0
    for attempt in range(MAX_PROMOTION_ATTEMPTS):
        state.check_number += 1
        healthy = check_health(state.server_id, state.check_number)
        if healthy:
            consecutive += 1
        else:
            consecutive = 0
        print("check", state.check_number, "healthy =", healthy)
        time.sleep(0.01)
        if consecutive == 3:
            state.status = ServerStatus.LIVE
            return True

    state.status = ServerStatus.FAILED        
    state.reason = f"never reached 3 consecutive healthy checks in {MAX_PROMOTION_ATTEMPTS} attempts" 
    return False        
    
def watch_promoted_servers(promoted: list[ServerState]) -> "ServerState | None":
    """
    Run a further round of health checks against every currently-promoted
    server, to catch post-promotion regressions (see srv-6 in the spec).

    Design decision for you to make and document: is a single unhealthy
    check here enough to call it a "regression", or do you want some
    confirmation (e.g. 2 consecutive fails) before declaring one — to avoid
    a false fleet-wide rollback triggered by ordinary transient flakiness?
    srv-6 goes permanently unhealthy from check_number >= 7 onward, so
    either approach will eventually catch it; the difference is false-alarm
    risk on the other, merely-flaky servers.

    Returns the first ServerState found to have regressed, or None if
    everything currently promoted is still healthy.
    """
    for server in promoted:
        consecutive_fails = 0
        for attempt in range(WATCH_MAX_CHECKS):
            server.check_number += 1
            healthy = check_health(server.server_id, server.check_number)
            print("watch check", server.server_id, server.check_number, "healthy =", healthy)
            if healthy:
                consecutive_fails = 0
            else:
                consecutive_fails += 1
                if consecutive_fails == 3:
                    return server
            time.sleep(0.01)

    return None


def rollout_canary() -> dict:
    """

    Deploys to FLEET one server at a time, in order:
      - For each server, attempt promote_server().
      - If promotion fails for a server, roll back every already-promoted
        server (set them to ServerStatus.ROLLED_BACK with a reason).
        Whether you then continue deploying to later servers in the queue
        or abort the whole rollout is your call — either is acceptable per
        the README, but document which you chose and why.

    Once the initial pass over the fleet is done, call
    watch_promoted_servers() against everything currently LIVE. If it
    reports a regression, roll back the ENTIRE fleet (every currently-live
    server, not just the regressing one) — mark them ROLLED_BACK with a
    reason referencing the regression.

    Invariant: no server is ever promoted or rolled back more than once.

    Returns final ServerState for every server in FLEET, keyed by
    server_id — this is what print_report() will render.
    """
    results = {}
    for server_id in FLEET:
        results[server_id] = ServerState(server_id=server_id)

    live_servers = []
    for server_id in FLEET:
        server = results[server_id]
        success = promote_server(server)
        print(server_id, "promoted =", success)
        if success:
            live_servers.append(server)
        else:
            for live in live_servers:
                live.status = ServerStatus.ROLLED_BACK
                live.reason = f"rolled back because {server_id} failed to stabilize"
            live_servers = []

    regressed = watch_promoted_servers(live_servers)
    if regressed is not None:
        for live in live_servers:
            live.status = ServerStatus.ROLLED_BACK
            live.reason = f"fleet-wide rollback: {regressed.server_id} regressed after promotion"

    return results


# ---------------------------------------------------------------------------
# Report + entry point
# ---------------------------------------------------------------------------

def print_report(results: dict) -> None:
    """
    Human-readable final report: which servers ended up live, which were
    rolled back or failed, and why (use each ServerState.reason).
    """
    for server_id, state in results.items():
        print(server_id, state.status, state.reason)


if __name__ == "__main__":
    results = rollout_canary()
    print_report(results)
