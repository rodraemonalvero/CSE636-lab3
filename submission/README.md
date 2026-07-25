\# Agent-Optimized CI Pipeline



\## Overview



This assignment implements an AI-assisted CI pipeline using Jenkins, Docker, Python, GitHub, and Claude.



The pipeline performs two automation tasks:



1\. Test-impact analysis to avoid running unnecessary tests.

2\. AI-assisted remediation for one controlled failure class: Black formatting failures.



The pipeline also includes a blocking human approval gate so the AI agent cannot apply changes automatically.



\---



\## Project Structure



```text

submission/

├── README.md

├── Jenkinsfile

├── requirements.txt

├── src/

│   ├── calculator.py

│   └── text\_utils.py

├── tests/

│   ├── test\_calculator.py

│   └── test\_text\_utils.py

├── scripts/

│   ├── select\_tests.py

│   └── remediation\_agent.py

├── docs/

│   └── guardrails.md

└── screenshots/

```



\---



\## Automation Task 1: Test-Impact Analysis



The `scripts/select\_tests.py` script examines changed files and selects only the tests related to those files.



Examples:



\- `src/calculator.py` selects `tests/test\_calculator.py`

\- `src/text\_utils.py` selects `tests/test\_text\_utils.py`

\- `README.md` or documentation-only changes skip application tests

\- unknown Python, dependency, or CI changes trigger the full test suite



This reduces unnecessary CI work and demonstrates build-skip logic.



\### Test-count evidence



The full test suite contains 10 tests.



The calculator-only selection contains 5 tests.



This shows that the pipeline can reduce the number of tests when only one module changes.



\---



\## Automation Task 2: Formatting Remediation



The controlled failure class is:



```text

Black formatting failure

```



The file `src/text\_utils.py` is intentionally valid Python but does not conform to Black formatting standards.



The remediation agent:



1\. Reads `format\_log.txt`

2\. Reads the affected source file

3\. Confirms the failure is a Black formatting issue

4\. Produces a formatting-only correction

5\. Prints the complete proposed file

6\. Leaves the original file unchanged

7\. Requires human approval before any proposal is accepted



The agent is not designed to fix arbitrary test failures, syntax errors, dependency problems, or security defects.



\---



\## Prompt Engineering



The system prompt is narrowly scoped.



It instructs Claude to:



\- handle only Black formatting failures

\- preserve program behavior exactly

\- modify only one Python source file under `src/`

\- return the complete formatted source file

\- avoid changing tests

\- avoid changing dependencies

\- avoid changing Jenkins configuration

\- avoid changing environment variables

\- avoid unrelated comments or logic

\- return the original source unchanged for unsupported failure classes



These restrictions reduce the blast radius of the AI agent.



\---



\## Human Approval Gate



The Jenkins pipeline uses a blocking `input` step.



After the remediation proposal is printed, Jenkins pauses and requires a human reviewer to choose:



```text

Proceed

```



or:



```text

Abort

```



The approval step is wrapped in a timeout.



If nobody responds, the pipeline aborts. It does not approve automatically.



\---



\## Guardrails



The main guardrails are:



\- remediation is limited to Black formatting failures

\- only files under `src/` are allowed

\- tests cannot be modified

\- dependencies cannot be modified

\- Jenkins configuration cannot be modified

\- environment variables and credentials cannot be modified

\- program logic must remain unchanged

\- the proposal is printed only

\- no code is merged automatically

\- a human must review the output



More detail is documented in:



```text

docs/guardrails.md

```



\---



\## Jenkins Pipeline Flow



The Jenkins pipeline performs these stages:



1\. Checkout the `agent-optimized-ci` branch

2\. Run test-impact selection

3\. Run only selected tests

4\. Skip application tests for documentation-only changes

5\. Run Black formatting check

6\. Call the remediation agent if formatting fails

7\. Pause at the human approval gate

8\. Archive test-selection and formatting logs



\---



\## Results



The implementation demonstrated:



\- the full suite contains 10 tests

\- calculator-only changes select 5 tests

\- text utility changes select only text utility tests

\- documentation-only changes skip application tests

\- Black detects one intentionally misformatted source file

\- the remediation agent correctly identifies the failure class

\- the agent proposes a valid formatting-only correction

\- the original source file remains unchanged

\- Jenkins blocks at a real human approval gate



\---



\## Screenshots



The `screenshots/` folder contains evidence for the lab and assignment, including:



\- local test execution

\- intentional formatting failure

\- test-impact analysis

\- remediation agent output

\- Jenkins approval gate

\- Jenkins pipeline success

\- Docker and Jenkins setup



\---



\## AI Tools Used



The following AI tools were used:



\- Claude through the Anthropic API for remediation analysis

\- ChatGPT for implementation guidance, troubleshooting, and documentation assistance



All AI-generated output was reviewed before use.



No AI-generated proposal was merged automatically.



\---



\## Reflection



One unexpected issue was that the remediation agent initially failed to read `format\_log.txt` because PowerShell created the redirected file using UTF-16 encoding while the Python script expected UTF-8.



I corrected this by recreating the log with:



```powershell

black --check src 2>\&1 | Out-File -Encoding utf8 .\\format\_log.txt

```



This showed that CI reliability depends not only on the AI agent but also on operating-system behavior, shell commands, encoding, dependencies, and the runtime environment.



Another surprise was that the Jenkins Docker image initially did not contain the Anthropic package. Rebuilding the custom Jenkins image resolved the issue.



These failures reinforced why the pipeline needs clear logs, limited agent scope, and human review.



\---



\## Conclusion



This project demonstrates how AI can improve CI efficiency by selecting relevant tests and proposing a controlled remediation.



The human approval gate and documented blast-radius limits ensure that the AI agent assists the developer without taking unsafe autonomous action.

