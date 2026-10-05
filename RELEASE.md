# GitSentry AI — Release & Tagging Guide (v1.0.0) 🚀

This document outlines the official process for tagging and publishing releases for **GitSentry AI**, verifying CI/CD pipelines, and integrating status badges.

---

## 📋 Release Checklist

Before tagging a new version, ensure the following criteria are met:

- [x] All unit tests pass: `pytest tests/ -v` (19/19 passed).
- [x] Security gate scan passes: `python gitsentry_analyzer.py user_service.py --fail-on High`.
- [x] Version strings updated in `core_engine.py`, `gitsentry_analyzer.py`, and `README.md`.
- [x] Dependencies documented in `requirements.txt`.
- [x] Clean git working tree (`git status` shows no uncommitted changes).

---

## 🏷️ Step 1: Git Tagging (`v1.0.0`)

Run the following commands in the root of your project:

```bash
# 1. Ensure you are on the main branch with the latest changes
git checkout main
git pull origin main

# 2. Stage all deliverables and commit
git add .
git commit -m "feat(release): GitSentry AI v1.0.0 official release"

# 3. Create an annotated git tag
git tag -a v1.0.0 -m "Release v1.0.0: AI-Powered Code Review & DevSecOps Gate"

# 4. Push commit and tags to GitHub
git push origin main
git push origin v1.0.0
```

---

## 🐙 Step 2: Create GitHub Release

You can publish the release using the **GitHub CLI** (`gh`) or through the **GitHub Web UI**.

### Option A: Using GitHub CLI (Fastest)

```bash
gh release create v1.0.0 \
  --title "GitSentry AI v1.0.0 — Production Release" \
  --notes-file RELEASE.md
```

### Option B: Via GitHub Web Interface

1. Navigate to your repository: `https://github.com/<your-username>/GitSentry-AI/releases`.
2. Click **"Draft a new release"**.
3. Select the tag `v1.0.0`.
4. Release Title: `GitSentry AI v1.0.0 — Production Release`.
5. Paste the release notes (see template below).
6. Click **"Publish release"**.

---

## 📝 Release Notes Template (v1.0.0)

```markdown
## What's New in v1.0.0 🎉

### 🛡️ Core Highlights
- **AI-Powered Code Review Engine**: Built with LangChain & Groq (`openai/gpt-oss-120b`) for sub-second, semantic SAST analysis.
- **Strict Pydantic Output**: Fully structured `ReviewReport` and `CodeIssue` schemas with severity classifications (Critical, High, Medium, Low).
- **Automated DevSecOps Security Gate**: `gitsentry_analyzer.py` integrates seamlessly into CI/CD pipelines to block insecure PRs.
- **Rich CLI UX**: Terminal styling, spinners, color-coded vulnerability matrices, and syntax-highlighted fix snippets.
- **Refactored Security Services**: Enterprise-grade `user_service.py` with Bcrypt password hashing, parameterized queries, and thread-safe batch operations.
- **Complete Test Coverage**: 19 automated Pytest unit tests covering security attack vectors, SQLite chunking, and environment policies.

### 🐛 Remediated CWEs & OWASP Vulnerabilities
- `CWE-89`: SQL Injection via parameterized queries.
- `CWE-327`: Broken cryptographic algorithms (MD5 upgraded to salted Bcrypt).
- `CWE-401 / CWE-404`: Database connection and cursor resource leaks resolved with context managers.
- `CWE-798`: Hardcoded credentials removed and externalized via `APP_SECRET_KEY`.
- `CWE-400`: SQLite host-parameter exhaustion avoided via query batching.
```

---

## 🛡️ Step 3: CI/CD & Badge Integration

Add the following dynamic status badges to the top of your `README.md` (replace `<your-username>` with your GitHub organization or account):

### 1. GitHub Actions Workflow Badge
```markdown
[![CI Pipeline](https://github.com/<your-username>/GitSentry-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-username>/GitSentry-AI/actions/workflows/ci.yml)
```

### 2. Release & Python Badges
```markdown
[![Latest Release](https://img.shields.io/github/v/release/<your-username>/GitSentry-AI?color=blue&logo=github)](https://github.com/<your-username>/GitSentry-AI/releases)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Powered by Groq](https://img.shields.io/badge/Powered%20By-Groq%20LPU-orange?logo=fastapi)](https://groq.com)
[![Security Gate](https://img.shields.io/badge/Security%20Gate-Passing-brightgreen?logo=shield)](https://github.com/<your-username>/GitSentry-AI)
```

---

## ⏪ Rollback Procedure

If a critical issue is discovered post-release:

```bash
# 1. Delete the local tag
git tag -d v1.0.0

# 2. Delete the remote tag on GitHub
git push origin --delete v1.0.0

# 3. Revert problematic commits and tag v1.0.1
git revert <commit-sha>
git push origin main
git tag -a v1.0.1 -m "Patch release v1.0.1"
git push origin v1.0.1
```
