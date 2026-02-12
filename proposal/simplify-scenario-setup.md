# Proposal: Simplify Scenario Setup with Docker Init Container

| Field       | Value                  |
|-------------|------------------------|
| Author      | @ningr                 |
| Created     | 2026-02-11             |
| Status      | **Draft**              |
| Finished    | —                      |

---

## Problem

Running a ClawBench scenario currently requires 4 steps and a local Python install:

```bash
pip install -r requirements.txt              # 1. install Python deps on host
python scripts/setup_scenario.py ... ...     # 2. generate config + copy workspace
cp .env.example .env                         # 3. add API key (one-time)
docker compose up --build                    # 4. start services
```

`setup_scenario.py` generates 3 artifacts that get volume-mounted into containers:
- `generated/openclaw.json` — OpenClaw gateway config with tool allow-list
- `workspace/AGENTS.md` — agent instructions (variant-specific)
- `generated/.env.scenario` — `SCENARIO=name` for mock server

This is confusing because:
- Users must install Python + PyYAML on the host before using Docker
- Users must remember to re-run setup when switching scenarios
- The generated files are invisible — easy to forget or use stale ones
- Two separate "run" concepts (setup vs start) for one logical action

## Goal

Single-command workflow, no host Python required:

```bash
cp .env.example .env                                          # one-time
SCENARIO=client_escalation docker compose up --build          # done
```

## Key Insight

All 5 scenarios use the **identical** tool allow-list:
`exec, slack, memory_search, memory_get, web_search, read`

The generated `openclaw.json` is the same for every scenario. This means we can use a **static config file** checked into the repo. The only per-scenario work is copying the right AGENTS.md variant and workspace files — which a lightweight Docker init container can handle.

## Design

```
                     docker compose up
                           |
                     [init container]        python:3.11-slim
                     reads SCENARIO + VARIANT env vars
                     copies AGENTS.md + workspace files
                           |
                     (exits 0)
                           |
              +------------+---------------+
              |                            |
        [mock-tools]                [openclaw-gateway]
        reads SCENARIO env          reads /workspace
        loads fixtures              reads config/openclaw.json
```

### Changes

#### Create: `config/openclaw.json` — static gateway config

Commit a single config with all 6 mock tools allowed + `session_status`. No more per-scenario generation. Mounted directly into gateway container.

#### Create: `Dockerfile.init` — init container image

Minimal `python:3.11-slim` image with PyYAML. Runs `scripts/init_workspace.py` and exits.

#### Create: `scripts/init_workspace.py` — workspace file copier

Focused script that reads `SCENARIO` and `VARIANT` from env vars, loads the scenario YAML, and copies the right files into `/workspace`. No config generation logic.

#### Modify: `docker-compose.yml`

- Add `init` service with `service_completed_successfully` dependency
- Mount `config/openclaw.json` instead of `generated/openclaw.json`
- Pass `SCENARIO` and `VARIANT` as env vars with defaults

#### Modify: `.env.example`

Add `SCENARIO` and `VARIANT` with comments listing available options.

#### Modify: `scripts/run.sh`

Remove `python scripts/setup_scenario.py` call. Remove pip prerequisite. Just validate `.env` and call `docker compose up` with env vars.

#### Modify: `scripts/test_full.sh` (Layer 4 only)

Replace `python scripts/setup_scenario.py` call with env var passthrough to docker compose.

#### Unchanged

- `scripts/setup_scenario.py` — kept for backward compat / `run_batch.py` use
- `scripts/run_batch.py` — manages its own config at runtime
- `scripts/run_episode.py` — just a client
- All scenario YAMLs and fixtures

## File Inventory

| Action | File                       | Purpose                                   |
|--------|----------------------------|-------------------------------------------|
| Create | `config/openclaw.json`     | Static gateway config (all tools allowed)  |
| Create | `Dockerfile.init`          | Init container image                       |
| Create | `scripts/init_workspace.py`| Workspace file copier (env var driven)     |
| Modify | `docker-compose.yml`       | Add init service, update mounts            |
| Modify | `.env.example`             | Add SCENARIO/VARIANT vars                  |
| Modify | `scripts/run.sh`           | Remove setup step                          |
| Modify | `scripts/test_full.sh`     | Remove setup step in Layer 4               |

## Verification

1. `docker compose up --build` with defaults — init runs, exits 0, services start
2. `SCENARIO=morning_brief docker compose up --build` — correct AGENTS.md copied
3. `SCENARIO=inbox_triage VARIANT=baseline docker compose up --build` — baseline variant
4. `python scripts/setup_scenario.py --list` — still works (backward compat)
5. `./scripts/test_full.sh --quick` — offline tests pass unchanged
6. `curl http://localhost:3001/health` — mock server healthy with correct scenario

---

## Dev Tracker

- [ ] Create `config/openclaw.json`
- [ ] Create `Dockerfile.init`
- [ ] Create `scripts/init_workspace.py`
- [ ] Update `docker-compose.yml`
- [ ] Update `.env.example`
- [ ] Update `scripts/run.sh`
- [ ] Update `scripts/test_full.sh`
- [ ] End-to-end verification
- [ ] Update README quick start section
