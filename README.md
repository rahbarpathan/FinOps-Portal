# CentrAlign AI — Autonomous AI Task Worker & FinOps Portal

> **Hiring Challenge Submission for AI Engineering Role**  
> A working prototype of an autonomous enterprise task worker that plans, operates in a real browser, recovers from runtime failures, gates high-risk decisions behind human approval, and verifies outcomes independently.

---

## 🌟 Executive Summary

Enterprise workflows require AI employees that can understand business objectives, navigate multiple enterprise portals, recover when APIs or UIs change or fail, follow company policies, and independently verify their work.

This repository implements a **fully functioning, narrow prototype** with zero simulated autonomy:
1. **Runtime Autonomy**: A ReAct (Reasoning + Action) execution loop where the LLM decides each next tool call dynamically based on runtime page observations, working memory, and objective context. **No hardcoded step sequences.**
2. **FinOps Enterprise Portal**: A realistic FastAPI mock environment featuring a **Vendor Accounts Inbox** (with multiple vendor emails, multiple invoices across dates, and messy formats) and an **Internal Finance System** (general ledger with strict validation rules).
3. **Chaos & Failure Recovery**: Built-in failure injection (HTTP 500 server errors on submit, altered UI layouts/button labels, slow loading, and initial validation errors) demonstrating automatic retry backoff and behavioral adaptation.
4. **Policy Enforcement & Human-in-the-Loop**: High-risk actions (e.g. invoices > $10,000 threshold) trigger policy checks and require operator sign-off via terminal prompt or interactive Web UI modal.
5. **Independent Outcome Verification**: A strictly isolated verification engine that inspects ground-truth database state (which the acting agent cannot see) to mathematically verify that the correct latest invoice was processed, amounts match, and zero duplicate bills were created.

---

## 📐 Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        USER NATURAL LANGUAGE TASK                      │
│   "Find latest invoice from Acme Corp, create bill in finance system"  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     AUTONOMOUS AI TASK WORKER LOOP                     │
│                                                                        │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐   │
│   │ Working      │ ──> │ Runtime LLM  │ ──> │ Native Tool Calling  │   │
│   │ Memory/Facts │     │ ReAct Engine │     │ (Browser, Files, HITL│   │
│   └──────────────┘     └──────────────┘     └──────────┬───────────┘   │
│          ▲                    ▲                        │               │
│          │                    │ Reflection / Retry     ▼               │
│          └─────────── Observation ◄───────── [Playwright Chromium]     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                   ┌────────────────┴────────────────┐
                   ▼                                 ▼
┌────────────────────────────────────┐ ┌─────────────────────────────────┐
│     MOCK COMPANY ENVIRONMENT       │ │  INDEPENDENT OUTCOME VERIFIER   │
│        (FinOps Portal)             │ │     (Isolated Ground-Truth)     │
│                                    │ │                                 │
│ • Vendor Inbox (Emails & Invoices) │ │ • Queries /api/ground-truth     │
│ • Internal Finance System (/bills) │ │ • Verifies LATEST date check    │
│ • Strict Validations (YYYY-MM-DD)  │ │ • Verifies exact amount & ledger│
│ • Chaos / Failure Injection Sandbox│ │ • Emits SHA-256 Audit Proof     │
└────────────────────────────────────┘ └─────────────────────────────────┘
```

---

## 🚀 Quickstart & Setup

### Prerequisites
- Python 3.11 or 3.12
- Google Chrome or Microsoft Edge installed on your system (Playwright connects automatically)
- Optional: `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` (if testing cloud LLMs). Zero-config offline autonomous engine works out-of-the-box!

### 1. Installation
Clone the repository and install dependencies:
```bash
# Using standard venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Or using uv (recommended for ultra-fast setup)
uv venv --python 3.12 .venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

### 2. Environment Configuration
Copy the template configuration:
```bash
cp .env.example .env
```
*(Optional: Add your `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` in `.env`)*

### 3. Start the Portal & Live Cockpit
```bash
python run.py --port 8000
```
Open your browser to:
- **Vendor Inbox**: [http://localhost:8000/inbox](http://localhost:8000/inbox)
- **Finance System**: [http://localhost:8000/bills](http://localhost:8000/bills)
- **Agent Live Cockpit**: [http://localhost:8000/agent](http://localhost:8000/agent)
- **Ground-Truth Isolated API**: [http://localhost:8000/api/ground-truth](http://localhost:8000/api/ground-truth)

### 4. Running the Agent via CLI
You can also run the agent directly from your terminal:
```bash
# Run latest invoice task
python run.py --cli "Find the latest invoice from Acme Corp, create a bill, and confirm." --reset

# Run high-value messy invoice with human approval policy
python run.py --cli "Process the pending invoice from Cyberdyne Systems and record the bill."
```

---

## 🧪 Hiring Evaluation Scenarios

The FinOps Portal includes 4 preset hiring test scenarios:

### Scenario 1: Date Comparison ("Latest Invoice")
- **Task**: `"Find the latest invoice from Acme Corp, compare dates to ensure it is the most recent, extract amount and due date, create a bill in our internal finance system, and confirm."`
- **Challenge**: Acme Corp has 3 invoices in the inbox (`2024-01-15`, `2024-03-20`, and `2024-05-10`). The agent must compare issue dates, identify `INV-ACM-103` ($8,250.00) as the latest, extract metadata, and register the bill.
- **Verification**: The verifier fails if older invoice `INV-ACM-101` or `INV-ACM-102` is selected.

### Scenario 2: Messy Invoice Formats & Policy Approval (> $10k)
- **Task**: `"Process the pending invoice from Cyberdyne Systems, extract details despite non-standard formatting, request human approval if amount exceeds $10k, and record the bill."`
- **Challenge**: Cyberdyne's invoice is raw text with date `"12th November 2024"` and amount `"$14,500.00 USD"`. The agent normalizes amount to `14500.00` and due date to `2024-12-12`. Because amount exceeds the $10,000 threshold, it gates execution and prompts for human authorization.

### Scenario 3: Chaos Recovery (500 Internal Server Error)
- **Task**: Submit invoice with 500 error injection active.
- **Challenge**: The server triggers HTTP 500 database lock timeout on first submit. The agent detects the error in its observation, reflects on the failure, retries with backoff, and completes submission.

### Scenario 4: Semantic UI Recovery (Changed Layout & Button Label)
- **Task**: Submit invoice with alternative layout mode.
- **Challenge**: The submit button label changes to *"Submit Payment Voucher"* and field layout rearranges. The agent discovers the new selector dynamically rather than relying on brittle hardcoded IDs.

---

## 🛡️ Independent Verification & Ground-Truth Isolation

To prevent prompt leaking or "self-grading" biases, verification is strictly isolated:
- The acting agent has access **only** to the browser and file tools.
- Upon completion, the `IndependentVerifier` queries `/api/ground-truth` (or direct SQLite state) independently.
- Verifies 5 objective criteria:
  1. Record created in `finance_bills`.
  2. Selected invoice is mathematically the latest among vendor emails.
  3. Payable amount matches ground truth to 2 decimal places.
  4. Due date adheres to strict `YYYY-MM-DD`.
  5. Zero duplicate records exist.
- Computes an immutable cryptographic signature (`PROOF-SHA256-...`) and links the full-page screenshot evidence.

---

## 📊 Evaluation Criteria Alignment

| Criterion | How This Prototype Demonstrates It |
|---|---|
| **Autonomy** | Every next step (browser navigation, filling, clicking, approval) is decided at runtime by the LLM function-calling loop. Zero hardcoded sequences. |
| **Execution** | Uses real Playwright Chromium to interact with live web elements, fill forms, and trigger HTTP requests. |
| **Reliability** | Built-in error observation, automatic retries on HTTP 500, self-correction on date format validation errors, and semantic button matching. |
| **Verification** | Ground-truth isolated audit engine checks ledger state and issues cryptographic proof hashes. |
| **Generalization** | Tool schemas and ReAct loop work across any web application; prompt-driven without domain-specific hardcoding. |
| **Engineering Quality** | Modular clean architecture (`src/portal`, `src/agent`, `src/tools`, `src/llm`), async Playwright, full pytest suite (15/15 passing), and rich CLI. |

---

## 🔬 Automated Pytest Suite

Run all automated unit and integration tests:
```bash
pytest tests/ -v
```
Tests cover:
- Inbox email parsing & attachment serving
- Finance bill validation rules (due date ISO format, numeric amount, duplicate rejection)
- Failure injection mechanisms (500 recovery, validation error recovery, alt button label)
- Independent verifier detection of older vs. latest invoices
- Working memory and fact tracking

---

## 🔮 What We Would Build Next
1. **Multi-Tab & Visual DOM Grounding**: Incorporate multimodal vision models (e.g. Gemini 2.5 Flash Multimodal) for coordinate-free canvas interaction on complex PDF tables.
2. **Dynamic Policy DSL**: Expand human approval checks into configurable declarative enterprise policies (e.g. per-department spending limits, vendor KYC verifications).
3. **Session Replay Video Artifacts**: Record WebM/WebP video streams of the agent's browser session for complete compliance auditing.
