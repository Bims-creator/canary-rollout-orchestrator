# DevOps Engineer Assessment — Canary Rollout Orchestrator

## What this assessment does

This is a **language-agnostic** problem — implement it in whatever language you like (Python, Node, Go, Java, Bash, etc.), standard library only, no install required. You're given a **fake fleet health-check API** (a stub you call directly in-process — no real network involved, no server to run) that deliberately misbehaves in a few realistic ways, and your job is to write an orchestrator that safely rolls a new version out to it.

### The fake fleet API (see `fake_fleet_spec.md` for exact behavior — implement a matching stub in your language)

`checkHealth(serverId)` returns whether a server is currently healthy after being deployed to. It has these deliberately-planted quirks:

1. **Flaky transient failures**: a healthy server occasionally reports unhealthy for a single check (roughly 1 in 6 checks) even though it's actually fine — distinct from a genuinely broken deploy.
2. **Post-promotion regression**: one specific server passes its initial health checks after deploy, gets promoted, and then *later* starts failing — your orchestrator must keep watching promoted servers, not just stop checking once promoted.
3. **A genuinely bad deploy**: one server never becomes healthy no matter how many times you check it.

### Requirements

Implement `rolloutCanary()` that:

1. Deploys to servers **one at a time** (in fleet order), and only promotes a server to "live" after **3 consecutive healthy checks** (with a short simulated delay between checks) — a single healthy check isn't enough, since transient flakiness could produce a false positive.
2. Distinguishes transient flakiness from a genuinely bad deploy — don't abort the whole rollout on the first unhealthy check; but *do* cap retries per server (document your limit) and abort deploying to that server (and roll back everything already promoted) if it never stabilizes.
3. Keeps monitoring already-promoted servers for a further round of checks after the rollout otherwise looks complete, and **rolls back the entire fleet** (not just the one regressing server) if any promoted server regresses afterward — treat that as a signal the new version is unsafe everywhere, not a per-server fluke.
4. Never promotes or rolls back the same server twice, and terminates with a clear final report: which servers ended up live, which were rolled back, and why.

### What we're actually evaluating

- Whether you correctly tell transient flakiness apart from a real failure (point above) instead of being trigger-happy or naive about retries — a surprisingly common bug in real rollout tooling.
- Whether your "keep watching after promotion" logic actually catches the regressing server, and whether your rollback decision is fleet-wide (correct) vs. per-server (misses the intent of the exercise).
- Whether your program terminates cleanly with a correct, human-readable report in all cases.

## Test cases

Run your orchestrator against the provided fake fleet API multiple times (the flakiness is randomized) and confirm across several runs:

1. The genuinely bad server never gets promoted, and its failure doesn't block servers that come after it in the queue from being evaluated (unless you choose to abort the whole rollout — either behavior is fine as long as it's a deliberate, documented decision, not an accident).
2. Transient flakiness on an otherwise-good server doesn't cause a false rollback.
3. The post-promotion regression is caught, and triggers a **fleet-wide** rollback, not just a rollback of that one server.
4. No server is promoted or rolled back more than once.

## How to submit

1. Commit your changes to your own repo using **the same email associated with your candidate account**.
2. Once ready, either reply to our team confirming you're ready to submit, **or** zip the `devops-engineer/` folder and upload it directly on our platform.

**Please note:** please don't generate the full solution entirely with AI tools — correctly distinguishing transient flakiness from a real failure, and getting the "watch after promotion, then roll back the whole fleet" logic right, is the actual point of this exercise. Using AI for a specific syntax lookup is fine.
