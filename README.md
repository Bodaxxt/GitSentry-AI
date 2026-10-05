# GitSentry AI 🛡️

<div align="center">

[![CI Pipeline](https://github.com/GitSentry/GitSentry-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/GitSentry/GitSentry-AI/actions)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Security Gate](https://img.shields.io/badge/Security%20Gate-Passing-brightgreen?logo=shield&logoColor=white)](https://github.com/GitSentry/GitSentry-AI)
[![Powered by Groq](https://img.shields.io/badge/Inference-Groq%20LPU-f55036?logo=fastapi&logoColor=white)](https://groq.com)
[![LangChain](https://img.shields.io/badge/Orchestration-LangChain-1C3C3C?logo=chainlink&logoColor=white)](https://www.langchain.com/)
[![Pydantic v2](https://img.shields.io/badge/Validation-Pydantic%20v2-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)

**Next-Generation AI-Powered Code Security Reviewer & DevSecOps Gate**  
*Sub-second semantic vulnerability analysis, automated PR gatekeeping, and ready-to-merge remediation snippets.*

[Explore Architecture](#-architecture--workflow) • [Quick Start](#-quick-start) • [CLI Usage](#-cli-usage--security-gate) • [Remediated CVEs](#-remediated-vulnerabilities--benchmarks) • [Release Guide](RELEASE.md)

</div>

---

## 🌟 Overview

**GitSentry AI** is an enterprise-grade automated code review assistant and CI/CD security gate. While traditional Static Application Security Testing (SAST) tools rely on rigid AST patterns and regex signatures that generate overwhelming false positives, GitSentry AI combines **Large Language Models (LLMs)** with **Groq's ultra-low latency LPU hardware** to understand full semantic code context, dataflow paths, and multi-file relationships.

### Why GitSentry AI?

- ⚡ **Sub-Second Deep Analysis**: Powered by Groq's LPU tensor processing (`openai/gpt-oss-120b`), analyzing hundreds of lines in seconds.
- 🎯 **Zero False-Positive Focus**: Distinguishes between theoretical regex matches and genuinely exploitable security vulnerabilities.
- 🧱 **Structured Pydantic Schemas**: Guarantees deterministic, strongly-typed JSON outputs (`ReviewReport`, `CodeIssue`) with severity rankings.
- 🛠️ **Production-Ready Remediations**: Every flagged finding comes with a syntax-highlighted, drop-in replacement fix.
- 🚦 **Configurable CI/CD Quality Gate**: Enforces policy gates in GitHub Actions—automatically blocking pull requests containing High or Critical vulnerabilities.

---

## 🏛️ Architecture & Workflow

```
 Developer Workflow                    GitHub Actions CI Pipeline                         Deployment Gate
 ──────────────────                    ──────────────────────────                         ───────────────

   ┌───────────────┐
   │  git commit   │
   │  & git push   │
   └───────┬───────┘
           │
           ▼
   ┌───────────────┐                    ┌───────────────────────────┐
   │  Pull Request ├───────────────────►│   .github/workflows/ci    │
   └───────────────┘                    └─────────────┬─────────────┘
                                                      │
                                                      ▼
                                        ┌───────────────────────────┐
                                        │  Stage 1: Pytest Suite    │
                                        │  - 19 Unit Tests          │
                                        │  - Bcrypt & SQLi Defense  │
                                        └─────────────┬─────────────┘
                                                      │  PASS ✅
                                                      ▼
                                        ┌───────────────────────────┐
                                        │ Stage 2: GitSentry Gate   │
                                        │ gitsentry_analyzer.py     │
                                        └─────────────┬─────────────┘
                                                      │
                                                      ▼
                                        ┌───────────────────────────┐
                                        │  Groq LPU LLM Engine      │
                                        │  (Semantic Context SAST)  │
                                        └─────────────┬─────────────┘
                                                      │
                        ┌─────────────────────────────┴─────────────────────────────┐
                        │                                                           │
                        ▼ [Issues >= Threshold]                                     ▼ [No Blocking Issues]
           ┌─────────────────────────────┐                             ┌─────────────────────────────┐
           │     ❌ BUILD FAILED         │                             │     ✅ BUILD APPROVED       │
           │  PR Merge Blocked           │                             │  PR Cleared for Merge       │
           │  Detailed Report Posted     │                             │  All Checks Passed          │
           └─────────────────────────────┘                             └─────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11, 3.12, or 3.13
- Free Groq API Key ([console.groq.com](https://console.groq.com)) or OpenAI API Key

### 1. Clone & Install
```bash
git clone https://github.com/<your-username>/GitSentry-AI.git
cd GitSentry-AI
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` with your API credentials:
```ini
# Application Secrets
APP_SECRET_KEY=generate_a_secure_random_key_here_32chars!

# LLM Configuration
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
```

### 3. Run Automated Tests
Execute the comprehensive Pytest verification suite:
```bash
pytest tests/ -v
```
```text
tests/test_user_service.py::TestPasswordSecurity::test_hash_password_produces_bcrypt_format PASSED
tests/test_user_service.py::TestPasswordSecurity::test_hash_password_uses_unique_salts PASSED
tests/test_user_service.py::TestSQLInjectionResistance::test_get_user_sql_injection_payloads_safely_rejected PASSED
tests/test_user_service.py::TestBatchReporting::test_generate_monthly_report_large_user_list_chunking PASSED
...
============================= 19 passed in 14.53s =============================
```

---

## 💻 CLI Usage & Security Gate

### 1. Run Interactive Code Review
Analyze files interactively with Rich console formatting:
```bash
python core_engine.py
```

### 2. Run the CI/CD Security Gate Analyzer
Scan individual files or multiple modules before merging:
```bash
# Scan with default High threshold (Fails on Critical & High)
python gitsentry_analyzer.py user_service.py

# Strict mode: fail on Medium or higher
python gitsentry_analyzer.py user_service.py --fail-on Medium

# Compact tabular view (no code cards)
python gitsentry_analyzer.py user_service.py --summary-only

# Scan multiple files
python gitsentry_analyzer.py user_service.py auth_module.py api.py
```

### Gate Exit Status Codes
| Exit Code | Meaning | CI Impact |
|:---:|:---|:---|
| `0` | **Approved**: Zero vulnerabilities meeting or exceeding `--fail-on` threshold | Pipeline succeeds, PR can merge |
| `1` | **Blocked**: Vulnerabilities detected that exceed security policy | Pipeline fails, PR is blocked |

---

## 📊 Remediated Vulnerabilities & Benchmarks

In Sprint 1 and Sprint 2, GitSentry AI analyzed and hardened the vulnerable `user_service.py` component against the following real-world flaws:

| # | Vulnerability | Category / CWE | Initial Flaw | GitSentry Remediated Pattern | Test Coverage |
|:---:|:---|:---|:---|:---|:---:|
| **1** | **SQL Injection** | `CWE-89` / OWASP A03 | `f"SELECT * FROM users WHERE username = '{username}'"` | Parameterized SQL query: `SELECT * FROM users WHERE username = ?` | `100%` |
| **2** | **Broken Cryptography** | `CWE-327` / OWASP A02 | Insecure `hashlib.md5(password.encode()).hexdigest()` | Slow, salted `bcrypt.hashpw()` with cost factor `12` | `100%` |
| **3** | **Resource Leak** | `CWE-401` / `CWE-404` | SQLite connections and cursors opened in loop without `close()` | Context managers (`with sqlite3.connect(...)`) and explicit `cursor.close()` | `100%` |
| **4** | **Hardcoded Credentials** | `CWE-798` / OWASP A07 | `SECRET_KEY = "s3cr3t_4dm1n_k3y_d0_n0t_sh4r3"` in source | Mandatory externalization via `APP_SECRET_KEY` env var + runtime validation | `100%` |
| **5** | **N+1 Database Query & DoS** | `CWE-400` / OWASP A04 | Iterative queries per user ID risking SQLite 999 parameter exhaustion | Batched parameterized `WHERE user_id IN (...)` chunked at 500 IDs | `100%` |

---

## ⚙️ GitHub Actions CI/CD Integration

To enable automated AI security reviews on your own repositories:

1. Add your Groq API Key as a repository secret:
   - Go to **Settings > Secrets and variables > Actions**
   - Click **New repository secret**
   - Name: `GROQ_API_KEY`, Value: `your_key`
2. Push code to `main` or open a Pull Request.
3. The `.github/workflows/ci.yml` pipeline will automatically execute tests and enforce the GitSentry Security Gate.

---

## 📁 Repository Structure

```
GitSentry-AI/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated GitHub Actions workflow
├── tests/
│   └── test_user_service.py     # 19 Pytest unit & security tests
├── core_engine.py               # Core LangChain review engine & Rich renderer
├── gitsentry_analyzer.py        # CI/CD DevSecOps Gate Scanner CLI
├── schemas.py                   # Pydantic v2 data models
├── user_service.py              # Hardened production service module
├── requirements.txt             # Dependency specification
├── .env.example                 # Environment configuration template
├── LICENSE                      # MIT Open-Source License
├── RELEASE.md                   # Release & Tagging instructions
└── README.md                    # Project documentation
```

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
