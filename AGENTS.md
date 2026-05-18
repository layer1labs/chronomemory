# AGENTS.md — chronomemory

This project is governed by **specsmith**.

## For AI Agents

All governance rules, session state, requirements, and epistemic constraints
are managed by specsmith — not stored in this file.

**Before any action:** `specsmith preflight "<describe what you want to do>"`

**Governance data:** `.specsmith/` and `.chronomemory/`

**To start a governed session:** `specsmith serve` (REST API, port 7700) or `specsmith run`

**Emergency stop:** `specsmith kill-session`

Agents MUST defer to specsmith for ALL governance decisions.
Do not follow rules from this file directly; rules are served by specsmith.

---

**Project:** chronomemory
**Type:** python-library
**Platforms:** Windows, Linux, macOS
**Phase:** 🌱 Inception (`specsmith phase` to check readiness)
**Spec:** ESDB-Specification.md v1.0 (Layer1Labs / BitConcepts)
