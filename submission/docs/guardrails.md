\# Guardrails



\## Human Approval



The remediation agent is not allowed to modify source code automatically.



After proposing a fix, Jenkins pauses and requires a human reviewer to approve the change before continuing.



This prevents accidental or harmful changes from being merged without review.



\---



\## Blast Radius Limits



The remediation agent only analyzes one known failure class:



\- calculator implementation errors



The agent is not allowed to:



\- modify unrelated source files

\- change project dependencies

\- edit CI configuration

\- create pull requests automatically



\---



\## Test Selection



The CI pipeline only runs tests related to modified files whenever possible.



Examples:



\- src/calculator.py → tests/test\_calculator.py

\- src/text\_utils.py → tests/test\_text\_utils.py

\- documentation-only changes skip application tests



\---



\## AI Usage



Claude was used only to analyze failing tests and generate a proposed fix.



The proposed fix is always reviewed by a human before acceptance.



No generated code is merged automatically.

