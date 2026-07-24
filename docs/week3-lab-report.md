\# Week 3 Lab — Build-Fixer Agent with Human Approval Gate



\## 1. Overview



This lab implements an AI-assisted CI pipeline using Jenkins. The objective was to create a workflow where an AI build-fixer agent detects a failed test, analyzes the failure, proposes a correction, and requires human approval before continuing.



The implementation uses Jenkins running inside Docker and integrates an AI agent to analyze build failures.



\---



\## 2. Pipeline Workflow



The implemented CI workflow:



1\. Checkout source code from GitHub.

2\. Run automated tests.

3\. Detect test failures.

4\. Execute the AI build-fixer agent.

5\. Generate root cause analysis and a proposed fix.

6\. Pause the pipeline for human approval.

7\. Continue after approval.



\---



\## 3. Intentional Build Failure



The project contained an intentional bug in the calculator application.



The incorrect implementation was:



```python

def add(a, b):

&#x20;   return a - b

