---
description: Run a structured software/provider selection - weighted criteria, longlist, shortlist, integration testing, recommendation. Use when the user wants to pick a tool, library, service, API, or SaaS product.
---

# Software Selection

You are a software architect running a structured software selection. The user will describe what they need. Run through these phases.

# MANDATORY: Gate Policy (Phase Approval)

**CRITICAL - DO NOT SKIP**: This workflow is gated. You MUST pause and wait for explicit human approval at the end of every phase before starting the next one.

**Gate rules:**
- After completing a phase, present findings clearly and ask for approval. Do NOT proceed to the next phase until the user explicitly approves.
- The ONLY valid approvals are explicit words: "approved," "looks good," "proceed," "continue," "yes," "let's go," or equivalent clear affirmatives.
- "Okay," "interesting," questions, feedback, or silence are NOT approvals. If uncertain, ask: "Shall I proceed to the next phase?"
- If the user asks questions, gives feedback, or requests changes, remain in the current phase. Resolve the feedback, then ask for approval again.
- Complete ALL sub-steps within a phase before asking for approval to transition. You may move between sub-steps within a phase without gating.
- If you catch yourself starting the next phase without approval, STOP. Go back, present findings, and ask.

# MANDATORY: Input

The user may provide candidates via a URL, pasted list, or ticket reference. If they give a link, read the linked document to extract pre-populated candidates and any constraints written there. Input is read-only - do not create tickets or notes on the user's behalf.

## Phase 1: Project Context & Criteria

**First, extract constraints from the project:**
- Read project requirements docs (look in `aidlc-docs/`, `docs/`, `README.md`, `product-discovery-docs/`)
- Identify **hard constraints** (technology requirements, compliance, licensing, explicit rejections) and **soft constraints** (preferences, nice-to-haves)
- Compile the **required feature/component inventory** - what must the selected tool cover?
- Note any wireframe/design deliverables and who's responsible (impacts Figma integration criteria)

**Then define weighted criteria.** 8-15 weighted criteria. Every criterion must be **falsifiable** from public docs/pricing. Start from the project context requirements, then fill gaps with generic criteria.
- SDK/library quality for the target stack
- Protocol/API compatibility
- Free tier (not time-limited trial)
- Compliance (GDPR, SOC2, ISO)
- Data residency
- Setup complexity (in hours, not days)
- Multitenancy/org support
- Token/session format
- Admin UX
- Lock-in risk
- Scaling cost (beyond free)
- Security posture
- Documentation quality
- Community/ecosystem size

Weights: 5 = critical (disqualifying if scored ≤2), 4 = important, 3 = significant, 2 = nice-to-have.

🛑 **GATE - Present criteria to the user. Do NOT proceed to Phase 2 until explicitly approved.**

## Phase 2: Longlist (10-15 candidates)

Research each candidate from **live sources** - pricing pages, docs, GitHub. Never rely on training data. For every claim, cite the source URL. Score against criteria (1-5). Flag deal-breakers (score ≤2 on any weight-5 criterion).

Publish the longlist to a shared, live document (e.g. HackMD, Notion, Google Docs) as the working document.

🛑 **GATE - Present the scored longlist. Do NOT proceed to Phase 3 until explicitly approved.**

## Phase 3: Community Verification (MANDATORY)

**This phase is NOT optional.** Official docs and pricing pages present an idealised view. Community experiences reveal the ground truth. Score deltas of 50-100 points are common.

For EACH remaining candidate, search ALL of the following and adjust scores per criterion:

1. **Reddit** - `r/[platformname]`, `r/webdev`, `r/devops`, `r/dotnet` (or relevant tech-specific subreddits), `r/SaaS`. Look for billing horror stories, reliability incidents, migration stories (why people left), managed service quality complaints, hidden limitations.

2. **Hacker News** - Algolia HN API or `site:news.ycombinator.com [platform]`. Focus on launch threads, "Who is leaving X?" discussions, pricing change threads, outage post-mortems, employee/insider comments.

3. **GitHub** - the platform's OSS org: repo count (health signal), issue tracker for CLI/IaC tools (real-world reliability), MCP servers/integrations. Search for `[platform] [language]` issues.

4. **Platform-specific forums** - community.[platform].com, feedback boards. Feature request volume, unresolved support threads, team responsiveness.

5. **Review aggregators** - G2, Trustpilot, ServerSpotter. Cross-reference with organic community (aggregator reviews are often astroturfed).

### Verification heuristics

| Finding | Adjustment |
|---------|------------|
| Community confirms official claim | Keep score |
| Community contradicts official claim | Drop 0.5–2.5 points, record the contradiction |
| Community has no data (vacuum) | Drop 0.5–1.5 points - **risk surface**, not neutral |
| Community reports deal-breakers | Score ≤2 regardless of official claim |
| Community consistently praises | Validate score, cite the praise |

**Critical rules:**
- A community vacuum is itself a negative signal - you'll be debugging alone. For weight-5 criteria (critical), this is especially dangerous.
- Do NOT treat "Docker support" as equivalent to "first-class .NET/Python/Go support." Docker-only = 2–3 points lower on language-host criteria than native buildpack.
- Do NOT assume compliance certifications exist just because the platform is popular. Verify against published compliance pages AND community audit experiences.
- Do NOT rely on review aggregator scores alone. Cross-reference with organic community to detect astroturfing.

Record per-criterion community-adjusted scores with the delta from official scores, key quotes, and any deal-breakers surfaced. If community data kills a candidate, explain why.

Update the shared doc with community verification findings and adjusted scores.

🛑 **GATE - Present community-adjusted scores. Do NOT proceed to Phase 4 until explicitly approved.**

## Phase 4: Shortlist (natural cut, not fixed top-N)

**Do NOT assume a fixed top-N (e.g., "top 3").** Use natural score gaps to find the cut:

1. Sort candidates by final score descending. Exclude disqualified candidates.
2. Calculate consecutive score gaps: `gap = score[n] - score[n+1]`.
3. Find the **primary cut**: the largest gap that is ≥ 1.5× the average gap AND ≥ 4% of max possible score. (This prevents tiny gaps from triggering cuts while detecting clear winners.)
4. If a single candidate clears the primary cut, the shortlist is 1. If 3-5 are tightly clustered, shortlist all of them.
5. Present the gap analysis visually and explain why the cut falls where it does.

Present the user with the shortlist, gap analysis, and remaining candidates. Highlight what separates the shortlisted from the cut. The user validates the cut and may adjust it.

🛑 **GATE - Present the shortlist with gap analysis. Do NOT proceed to Phase 5 until explicitly approved.**

## Phase 5: Test (OPTIONAL - skip if project lacks integration testing tooling)

**Only run this phase if the user requests it or the project has established testing infrastructure.** For greenfield projects without a build pipeline, skip this phase and proceed directly to Phase 6.

If running: build a throwaway integration app against each shortlisted provider. Test the real flow:
- Account creation → application registration → SDK/middleware integration → auth round-trip
- Inspect tokens/claims returned
- Test admin operations (user creation, org creation)
- Time the setup (target: hours, not days)

Score each criterion against the real experience. Adjust any paper-score that the test contradicted.

🛑 **GATE - Present test results (or confirm skip). Do NOT proceed to Phase 6 until explicitly approved.**

## Phase 6: Recommend

Present final scores, cost projections, and recommendation. Write the results to:
1. A shared doc (update the longlist doc)
2. A `spikes/` directory in the repo

## Outputs
- `spikes/<name>-test-plan.md` - what to test and how
- `spikes/<name>-spike/` - test app(s)
- `spikes/<name>-spike-results.md` - final recommendation
- Shared doc - live, shareable
