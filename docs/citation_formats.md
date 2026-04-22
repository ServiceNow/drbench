# DRBench Citation Format Guide

This document describes the citation formats expected by the DRBench evaluation metrics (insights recall and factuality). Agents that produce correctly-formatted citations will score higher because the automated evaluator can verify them against the enterprise environment.

## Overview

The evaluation pipeline normalizes agent citations through `drbench/agents/citation_normalizer.py` and then verifies them by retrieving the cited content from the enterprise environment. Citations that can't be parsed result in failed factuality checks.

## Source Types and Expected Formats

### Mattermost Messages

The evaluator expects **user**, **team**, and **channel** to be identifiable. Omitting any of these fields will cause the citation to fail validation.

**Accepted formats** (in order of reliability):

```
(User: john.doe, Team: compliance_team, Channel: general)
Mattermost Message - Enterprise Chat (User: john.doe, Team: Compliance, Channel: General)
MatterMost chat from user john.doe in team Compliance channel General
```

**Normalized to:** `MatterMost_<channel>_<team>_<user>`

**Common mistakes that fail validation:**
```
Mattermost, Market Research Team Channel     <-- missing user and team
Mattermost post by jwang                      <-- missing team and channel
Mattermost (channel: general)                 <-- missing user and team
```

### Email / RoundCube

The evaluator expects at least a **sender email address**.

**Accepted formats:**

```
Email from sarah.johnson@company.com to bob@company.com with subject Q3 Report
Email from sarah.johnson@company.com on 20 Jan 2025
**Q3 Report** - Email from sarah.johnson@company.com
```

**Normalized to:** `RoundCube-<from>-<to>-<subject>`

### Files (Nextcloud / FileBrowser)

Use the **exact filename** as it appears in the file system.

**Accepted formats:**

```
centennial-shopper-experience.pdf
shared/reports/centennial-shopper-experience.pdf
Nextcloud File (shared/centennial-shopper-experience.pdf)
```

**Normalized to:** just the filename, e.g. `centennial-shopper-experience.pdf`

### Web URLs

Return the full URL as-is:

```
https://example.com/article
```

## Internal Representation

After normalization, citations are converted to an internal `<sep>`-delimited format for content retrieval:

- Mattermost: `mattermost<sep>channel<sep>team<sep>user`
- Email: `roundcube<sep>from<sep>to<sep>subject`
- Files: the filename string directly

The validation at `drbench/agents/utils.py:get_content()` splits on `<sep>` and expects exactly 4 parts for Mattermost citations. Citations that don't split into 4 parts log a warning and return `None`, causing the factuality check to fail for that insight.

## Recommendations for Agent Developers

1. When citing Mattermost messages, always capture the **username**, **team name**, and **channel name** from the search results and format them explicitly.
2. When citing emails, include the **sender's email address** at minimum.
3. When citing files, use the **exact filename** as returned by search/download tools.
4. Avoid vague citations like "internal documents" or "team discussions" -- the evaluator cannot verify these.
