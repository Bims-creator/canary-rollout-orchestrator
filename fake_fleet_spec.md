# Fake Fleet Health-Check Spec — implement this stub yourself in your chosen language

There is no real fleet for this assessment — implement a local function/stub matching
this behavior and call it in-process from your `rolloutCanary()` orchestrator.

## The fleet

6 servers total, IDs `srv-1` through `srv-6`, deployed to **in that order**.

## Function signature (adapt naming to your language's conventions)

```
checkHealth(serverId: string, checkNumber: int) -> bool
```

`checkNumber` is a monotonically increasing counter *per server* that you pass in —
starting at 1 for the first time you ever check that server, incrementing by 1 each
time you check it again (including checks after promotion). Your stub uses this to
decide what to return deterministically-but-randomly per the rules below.

## Per-server behavior

- **`srv-1`, `srv-2`, `srv-3`, `srv-5`, `srv-6` — normal servers with transient flakiness.**
  Each check has an independent ~1-in-6 chance of returning `false` (unhealthy) even
  though the server is fine. There is no upper bound on how many times a single check
  might randomly come back unhealthy in a row (it's independent per call), but in
  practice it will very rarely take more than a handful of retries to see 3
  consecutive `true` results.

- **`srv-4` — genuinely bad deploy.** Always returns `false`, no matter how many times
  you check it or how high `checkNumber` goes.

- **`srv-6` — the post-promotion regression.** Behaves like a normal flaky server
  (per above) for its first 3 consecutive-healthy sequence (i.e. it *will* get
  promoted), but starting at `checkNumber >= 7` for this server, it always returns
  `false` from then on — simulating a problem that only shows up a little while after
  the server went live.

## Suggested stub skeleton (pseudocode — adapt to your language)

```
def checkHealth(serverId, checkNumber):
    if serverId == "srv-4":
        return False
    if serverId == "srv-6" and checkNumber >= 7:
        return False
    return random() > (1/6)   # ~83% healthy, ~17% transient flake
```

## Determinism note

Since the flaky behavior is randomized, run your orchestrator a few times to build
confidence it behaves correctly across different random outcomes, not just once.
