## 1. General Operational Rules
These rules apply to every ticket and interaction to ensure we maintain control over the repository's scope and quality.

* Implement one ticket only.
* Do not implement future-ticket features.
* Do not refactor unrelated systems.
* Do not introduce new architecture unless explicitly required by the ticket.
* Avoid unnecessary dependencies.
* Run build/tests when possible before finalizing.
* Report all follow-ups or out-of-scope issues separately; do not fix them automatically.
* Never over-engineer a problem, find a suitable solution to the MVP.
* Models should be seperated in models.py
* Paramters must be set at config/settings.yaml

## 2. Architecture-Specific Rules
This project is a React-style MVP utilizing FastAPI, LangChain, and Langfuse. Strict adherence to these architectural boundaries is required.

* Maintain strict layer isolation: Keep the API layer, Application service, Agent runtime, and Tracing layer entirely separated.
* API Agnosticism: The API layer must not know how the agent is built internally.
* Route Constraints: FastAPI routes must never own LangChain logic directly.
* Tracing Boundaries: Keep tracing localized to its respective layer; do not let Langfuse or tracing concerns leak across the entire codebase.


## 3. Branching Strategy
* Use branches per ticket.
* For each ticket flow: main ↓ feature/t0001-project-skeleton ↓ test ↓ merge ↓ feature/t0002-core-model.

## 4. Manual Verification
* Always add manual verification that the developer can test after make changes not just  "build passed".
* Every ticket should have a small manual checklist.


## 5. Completion Report Requirement
At the end of every ticket execution, a completion report must be generated. The report must strictly include:

* Summary of changes.
* Files created, changed, or modified.
* Commands executed/run.
* Build and test results.
* Specific manual verification steps required to validate the ticket.
* Risks.
* Follow-up tickets.
* Docs that need updating.

## 6. Repo-State Updates
Update a Repo_Current_State.md file after completion. Include the following:

* Current branch.
* Completed tickets.
* Current folder structure.
* Installed dependencies.
* Available scripts.
* Build/test status.
* Known issues.
* Next recommended ticket.