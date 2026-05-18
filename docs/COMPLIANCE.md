# Compliance Report — chronomemory

**Generated:** 2026-05-18

## Project Summary

*Could not parse scaffold.yml*

## Requirements Coverage Matrix

**Coverage**: 0/14 (0%)

- ✗ REQ-CM-001
- ✗ REQ-CM-002
- ✗ REQ-CM-003
- ✗ REQ-CM-004
- ✗ REQ-CM-005
- ✗ REQ-CM-006
- ✗ REQ-CM-007
- ✗ REQ-CM-008
- ✗ REQ-CM-009
- ✗ REQ-CM-010
- ✗ REQ-CM-011
- ✗ REQ-CM-012
- ✗ REQ-CM-013
- ✗ REQ-CM-014

## Audit Summary

- **Passed**: 27
- **Failed**: 1
- **Fixable**: 0
- **Status**: Issues found

- ✓ Required file AGENTS.md exists
- ✓ Required file LEDGER.md exists
- ✓ Governance file docs/governance/RULES.md exists
- ✓ Governance file docs/governance/SESSION-PROTOCOL.md exists
- ✓ Governance file docs/governance/LIFECYCLE.md exists
- ✓ Governance file docs/governance/ROLES.md exists
- ✓ Governance file docs/governance/CONTEXT-BUDGET.md exists
- ✓ Governance file docs/governance/VERIFICATION.md exists
- ✓ Governance file docs/governance/DRIFT-METRICS.md exists
- ✓ Recommended file docs/REQUIREMENTS.md exists
- ✓ Recommended file docs/TESTS.md exists
- ✓ Recommended file docs/ARCHITECTURE.md exists
- ✓ Recommended file docs/SPECSMITH.yml exists
- ✓ Recommended file CONTRIBUTING.md exists
- ✓ Recommended file LICENSE exists
- ✗ 14 REQ(s) without test coverage: REQ-CM-001, REQ-CM-002, REQ-CM-003, REQ-CM-004, REQ-CM-005, REQ-CM-006, REQ-CM-007, REQ-CM-008, REQ-CM-009, REQ-CM-010, REQ-CM-011, REQ-CM-012, REQ-CM-013, REQ-CM-014
- ✓ LEDGER.md has 37 lines (within 500 threshold)
- ✓ 0 open, 0 closed TODOs
- ✓ AGENTS.md: 86 lines
- ✓ docs/governance/RULES.md: 20 lines
- ✓ docs/governance/SESSION-PROTOCOL.md: 7 lines
- ✓ docs/governance/LIFECYCLE.md: 4 lines
- ✓ docs/governance/ROLES.md: 4 lines
- ✓ docs/governance/CONTEXT-BUDGET.md: 67 lines
- ✓ docs/governance/VERIFICATION.md: 3 lines
- ✓ docs/governance/DRIFT-METRICS.md: 3 lines
- ✓ Trace vault intact (2 seals)
- ✓ Phase 🚀 Release: 100% ready

## Recent Activity

- `7249e41 fix: resolve all CI failures (ruff lint + zero-deps check)`
- `ef086d7 feat: initial release — chronomemory ESDB v0.1.0`

**Contributors:**
- 2	Tristen Pierson

## AI System Inventory (REG-010)

### Agent Capabilities
- **run_shell**: Execute a shell command. Safety-checked; destructive commands are blocked.
  *Epistemic claims:* EXEC-001: no python -c for non-trivial code
- **read_file**: Read a text file from the repository.
  *Epistemic claims:* read-only: does not modify files
- **write_file**: Write content to a file (creates or overwrites).
  *Epistemic claims:* modifies filesystem: logged in audit chain
- **patch_file**: Apply a unified diff patch to a file.
  *Epistemic claims:* modifies filesystem: logged in audit chain
- **list_files**: List files matching a glob pattern in a directory.
  *Epistemic claims:* read-only: does not modify files
- **grep**: Search for a pattern in files.
  *Epistemic claims:* read-only: does not modify files
- **git_diff**: Show the git diff for the working tree.
  *Epistemic claims:* read-only: does not modify files
- **git_status**: Show git status for the working tree.
  *Epistemic claims:* read-only: does not modify files
- **run_tests**: Run the project test suite.
  *Epistemic claims:* may modify test artifacts but not source
- **open_url**: Fetch text content from a URL.
  *Epistemic claims:* network: reads external resources
- **search_docs**: Search documentation files in the repo.
  *Epistemic claims:* read-only: does not modify files
- **remember_project_fact**: Store a named fact in the local project index (.repo-index/facts.json).
  *Epistemic claims:* modifies .repo-index/facts.json only
- **run_gcc**: Compile or build with GCC / G++. Pass compiler flags verbatim via *args*. Use *compiler* to select g++, gcc-12, etc.
  *Epistemic claims:* invokes compiler process; may produce build artifacts
- **run_arm_gcc**: Cross-compile for ARM bare-metal (arm-none-eabi-gcc / g++). Set *compiler* to 'arm-none-eabi-g++' for C++.
  *Epistemic claims:* invokes cross-compiler; produces .elf/.bin artifacts
- **run_aarch64_gcc**: Cross-compile for AArch64 Linux (aarch64-linux-gnu-gcc / g++).
  *Epistemic claims:* invokes cross-compiler; produces shared/static libraries
- **run_iar_compiler**: Build an IAR Embedded Workbench project via IarBuild command-line. Provide the .ewp *project_file* path.
  *Epistemic claims:* requires IAR Embedded Workbench installed; produces .out artifacts
- **run_intel_compiler**: Compile with Intel oneAPI (icx/icpx) or classic (icc/icpc) compilers. Use *compiler* to select the binary.
  *Epistemic claims:* requires Intel oneAPI or classic compiler installed
- **run_clang_format**: Run clang-format on source files. Use *in_place=True* to apply changes, or leave False to print the diff only.
  *Epistemic claims:* modifies source files in-place when in_place=True
- **run_clang_tidy**: Run clang-tidy static analysis on source files. Pass *checks* to filter specific lint rules.
  *Epistemic claims:* read-only analysis unless --fix is passed
- **run_vsg**: Run VSG (VHDL Style Guide) on .vhd/.vhdl files or directories. Use *fix=True* to apply automatic style corrections in place.
  *Epistemic claims:* modifies VHDL source files in-place when fix=True

### Risk Classification
- **EU AI Act tier**: GPAI (general-purpose; systemic risk assessment required if >10^25 FLOP)
- **NIST AI RMF**: GOVERN + MAP + MEASURE + MANAGE controls applied
- **Use-case scope**: software development governance; not Annex III high-risk

### Human Oversight Controls
- Preflight gate: all governed actions require human-language approval
- Kill-switch: `specsmith kill-session` halts all active agent sessions
- Escalation: `specsmith preflight --escalate-threshold <float>` gates low-confidence actions
- Retry budget: `agents_max_iterations` in docs/SPECSMITH.yml bounds self-improvement loops

## Governance File Inventory

- ✓ `AGENTS.md`
- ✓ `LEDGER.md`
- ✓ `docs/SPECSMITH.yml`
- ✗ `scaffold.yml`
- ✓ `docs/REQUIREMENTS.md`
- ✓ `docs/TESTS.md`
- ✓ `docs/ARCHITECTURE.md`
- ✓ `docs/governance/RULES.md`
- ✓ `docs/governance/SESSION-PROTOCOL.md`
- ✓ `docs/governance/LIFECYCLE.md`
- ✓ `docs/governance/ROLES.md`
- ✓ `docs/governance/VERIFICATION.md`
