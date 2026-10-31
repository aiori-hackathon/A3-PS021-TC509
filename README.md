# SENTRY-6G

**A Failure-Aware Dialog Continuity and Safe Recovery Framework for Heterogeneous AI-Agent Networks**

**AIORI-3 Hackathon | Problem Statement PS-021**

**Team:** Team Sync  
**Team Code:** A3-PS021-TC509

## Project Overview

SENTRY-6G is a prototype developed for PS-021, *Experimental Dialog Correlation and Recovery Across Agent Adapters*.

The project addresses a problem in distributed agent communication: when a connection fails or an acknowledgement is lost, the requesting agent may not know whether an operation was completed. Retrying without checking can result in duplicate execution.

SENTRY-6G explores this problem through a three-service architecture that maintains persistent dialog identities, tracks operation states, and uses executor-side evidence to support recovery decisions.

The current implementation uses mock agent adapters and simulated network faults. It is intended as an experimental prototype relevant to reliable coordination in future distributed and 6G-oriented agent systems.

## Implemented Features

- Persistent dialog identification and lifecycle tracking
- Recovery based on executor-side evidence
- Duplicate-effect prevention using idempotent execution
- SQLite-backed dialog journals and executor records
- Simulation of five communication-failure scenarios
- Browser-based monitoring dashboard
- Automated tests and reproducible demonstration scripts

## Working Prototype

The complete application, installation instructions, tests and validation reports are available in the `SENTRY-6G` directory.

**[View Source Code and Setup Instructions](SENTRY-6G/README.md)**

**[View Automated Tests](SENTRY-6G/tests/)**

**[Run the Five-Scenario Demonstration](SENTRY-6G/judge_demo.py)**

**[View Validation Report](SENTRY-6G/reports/judge-demo-20261031T181852Z.md)**

**[View Machine-Readable Results](SENTRY-6G/reports/judge-demo-20261031T181852Z.json)**

### Validation Summary

The prototype passed 11 automated tests and five simulated fault-recovery scenarios.

The five-scenario demonstration produced four new executor effects, matching the expected count. The partition-before-dispatch scenario produced no effect.

These results apply to the local mock-adapter environment. The prototype has not been evaluated on a physical 6G network.

## Project Demonstration

[Watch Team Sync's Project Demonstration](https://youtu.be/9SmCgGLCSf8)

This video provides the team's project overview and technical presentation. The runnable implementation and reproducible validation evidence are available in the repository.

## Team Members

- Shriyam Adya Sharma
- Shreyas G

---

**Team Sync | A3-PS021-TC509 | AIORI-3 Hackathon**
