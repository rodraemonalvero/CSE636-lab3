\# Guardrails



\## Purpose



This project demonstrates a safe AI-assisted CI pipeline. The remediation agent is intentionally limited to a single failure class to minimize risk.



\---



\# Human Approval Gate



The remediation agent never modifies source code automatically.



Instead, it:



1\. Detects a supported failure.

2\. Generates a proposed fix.

3\. Prints the proposal.

4\. Waits for a human reviewer.



Jenkins pauses with a blocking approval gate.



The reviewer must explicitly select \*\*Proceed\*\* or \*\*Abort\*\* before the pipeline continues.



If no response is received before the timeout, the pipeline fails safely.



\---



\# Allowed Failure Class



The remediation agent supports only one failure type:



\*\*Black formatting failures\*\*



It may analyze Python files located under:



```

src/

```



and propose formatting-only corrections.



\---



\# Blast Radius Limits



The remediation agent is NOT allowed to:



\- modify tests

\- change application behavior

\- change algorithms

\- edit Jenkins configuration

\- install packages

\- modify dependencies

\- change environment variables

\- modify files outside `src/`

\- automatically merge code

\- automatically create pull requests



Any unsupported failure is reported without proposing changes.



\---



\# Test Selection



The pipeline performs simple test-impact analysis.



Mappings include:



\- `src/calculator.py` → `tests/test\_calculator.py`

\- `src/text\_utils.py` → `tests/test\_text\_utils.py`



Documentation-only changes skip application tests.



Unknown changes trigger the complete test suite.



\---



\# Human Review Checklist



Before approving a proposal, the reviewer verifies:



\- the failure is formatting-only

\- only one source file is affected

\- no logic changes exist

\- no dependency changes exist

\- no CI configuration changes exist

\- the proposal follows Black formatting rules



\---



\# AI Usage



Claude analyzes the formatting failure and proposes a corrected version of the source file.



The proposal is reviewed by a human before acceptance.



No generated code is merged automatically.

