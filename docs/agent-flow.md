<!-- AUTO-GENERATED — Do not edit. Edit config/agent-flow.yaml instead. -->
<!-- Last generated: 2026-02-21 04:35 UTC -->
<!-- Regenerate: python scripts/validate-flow.py --mermaid -o docs/agent-flow.md -->

# Agent Flow Graph

Visual representation of how agents interact through dispatches, events, and triggers.

**Source of truth**: `config/agent-flow.yaml` (v2 schema)

**Legend:**
- **Blue** = Core dev loop (triage, PO, engineers, reviewers)
- **Green** = Strategic (PM, analysts)
- **Teal** = Tech Lead (multi-job agent)
- **Orange** = Operations (SRE, QA, customer ops, human ops)
- **Purple** = Content (creator, UX)
- **Grey** = Infrastructure workflows (deploy, ingest, CI)
- **Pink** = External triggers (PRs, issues, alerts)
- **Solid arrows** = `repository_dispatch` (event-based)
- **Dashed arrows** = `workflow_run` or external trigger
- **`*`** = dispatch happens inside agent session (not in workflow YAML)

```mermaid
flowchart TD

    subgraph core[Core Dev Loop]
        TRIAGE[Triage]
        PRODUCT_OWNER[Product Owner]
        ENGINEER[Engineer]
        OPS_ENGINEER[Ops Engineer]
        REVIEWER[Reviewer]
    end

    subgraph strat[Strategic / Intelligence]
        STRATEGIC[Strategic]
        PRODUCT_ANALYST[Product Analyst]
        FINANCIAL_ANALYST[Financial Analyst]
        MARKETING_STRATEGIST[Marketing Strategist]
    end

    subgraph techlead[Tech Lead]
        TECH_LEAD_FULL_SCAN[Full Scan (daily)]
        TECH_LEAD_ARCHITECTURE_REVIEW[Architecture Review (daily)]
        TECH_LEAD_TECH_DEBT_SCAN[Tech Debt Scan (daily)]
        TECH_LEAD_HARNESS_REQUEST_REVIEW[Harness Request Review (daily)]
        TECH_LEAD_SECURITY_SCAN[Security Scan (daily)]
        TECH_LEAD_QA_TOOLING_REVIEW[Qa Tooling Review (daily)]
        TECH_LEAD_INFRASTRUCTURE_REVIEW[Infrastructure Review (daily)]
        TECH_LEAD_DOC_REVIEW[Doc Review (daily)]
        TECH_LEAD_TEST_REVIEW[Test Review (daily)]
        TECH_LEAD_PROJECT_STRUCTURE_REVIEW[Project Structure Review (daily)]
        TECH_LEAD_PIPELINE_QUALITY_REVIEW[Pipeline Quality Review (daily)]
    end

    subgraph ops[Operations]
        SITE_RELIABILITY[Site Reliability]
        QA_ANALYST[Qa Analyst]
        CUSTOMER_OPS[Customer Ops]
        HUMAN_OPS[Human Ops]
        ESCALATION_LEAD[Escalation Lead]
    end

    subgraph content[Content]
        CONTENT_CREATOR[Content Creator]
        USER_EXPERIENCE[User Experience]
    end

    subgraph infra_wf[Infrastructure]
        DEPLOY_WF[Deploy]:::infraStyle
        PR_MANAGER_WF[Pr Manager]:::infraStyle
        QA_TRIAGE_WF[Qa Triage]:::infraStyle
        INGEST_WF[Ingest]:::infraStyle
        CI_WF[Ci]:::infraStyle
    end

    ISSUE_OPENED{{Issue Opened}}:::external
    ISSUE_LABELED{{Issue Labeled}}:::external
    PR_OPENED{{PR Opened}}:::external
    PR_MERGED{{PR Merged}}:::external
    CHECK_SUITE{{Check Suite}}:::external
    AZURE_ALERT{{Azure Alert}}:::external

    TRIAGE -.->|"batch≥5"| PRODUCT_OWNER
    PRODUCT_OWNER -.->|"unassigned>0 *"| ENGINEER
    PRODUCT_OWNER -.->|"agent decision *"| USER_EXPERIENCE
    ENGINEER -.->|"idle, PM>2h"| STRATEGIC
    REVIEWER -->|"changes requested"| ENGINEER
    REVIEWER -->|"changes requested"| OPS_ENGINEER
    REVIEWER -.->|"batch≥5"| PRODUCT_OWNER
    REVIEWER -.->|"untriaged source/tech-lead"| TECH_LEAD
    STRATEGIC -.->|"always"| PRODUCT_OWNER
    SITE_RELIABILITY -.->|"agent decision *"| INGEST_WF
    TECH_LEAD_FULL_SCAN -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_ARCHITECTURE_REVIEW -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_TECH_DEBT_SCAN -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_SECURITY_SCAN -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_QA_TOOLING_REVIEW -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_INFRASTRUCTURE_REVIEW -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_DOC_REVIEW -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_TEST_REVIEW -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_PROJECT_STRUCTURE_REVIEW -.->|"always"| PRODUCT_OWNER
    TECH_LEAD_PIPELINE_QUALITY_REVIEW -.->|"always"| PRODUCT_OWNER

    ISSUE_OPENED -.-> TRIAGE
    ISSUE_LABELED -.-> ENGINEER
    PR_MERGED -.-> ENGINEER
    CHECK_SUITE -.-> ENGINEER
    ISSUE_LABELED -.-> OPS_ENGINEER
    AZURE_ALERT -.-> SITE_RELIABILITY

    classDef external fill:#f9f,stroke:#333,stroke-width:1px
    classDef core fill:#4a9eff,stroke:#333,color:#fff
    classDef strat fill:#2ecc71,stroke:#333,color:#fff
    classDef opsStyle fill:#e67e22,stroke:#333,color:#fff
    classDef contentStyle fill:#9b59b6,stroke:#333,color:#fff
    classDef infraStyle fill:#95a5a6,stroke:#333,color:#fff
    classDef techleadStyle fill:#1abc9c,stroke:#333,color:#fff
    class TRIAGE core
    class PRODUCT_OWNER core
    class ENGINEER core
    class OPS_ENGINEER core
    class REVIEWER core
    class STRATEGIC strat
    class PRODUCT_ANALYST strat
    class FINANCIAL_ANALYST strat
    class MARKETING_STRATEGIST strat
    class SITE_RELIABILITY opsStyle
    class QA_ANALYST opsStyle
    class CUSTOMER_OPS opsStyle
    class HUMAN_OPS opsStyle
    class ESCALATION_LEAD opsStyle
    class CONTENT_CREATOR contentStyle
    class USER_EXPERIENCE contentStyle
    class TECH_LEAD_FULL_SCAN techleadStyle
    class TECH_LEAD_ARCHITECTURE_REVIEW techleadStyle
    class TECH_LEAD_TECH_DEBT_SCAN techleadStyle
    class TECH_LEAD_HARNESS_REQUEST_REVIEW techleadStyle
    class TECH_LEAD_SECURITY_SCAN techleadStyle
    class TECH_LEAD_QA_TOOLING_REVIEW techleadStyle
    class TECH_LEAD_INFRASTRUCTURE_REVIEW techleadStyle
    class TECH_LEAD_DOC_REVIEW techleadStyle
    class TECH_LEAD_TEST_REVIEW techleadStyle
    class TECH_LEAD_PROJECT_STRUCTURE_REVIEW techleadStyle
    class TECH_LEAD_PIPELINE_QUALITY_REVIEW techleadStyle
```

## Events

| Event | Description | Status |
|-------|-------------|--------|
| `agent-product-manager-feedback` | PM flagged misalignment, PO should re-scope | stub |
| `agent-product-owner-complete` | PO finished triaging, unassigned work exists (payload: chain_depth) | active |
| `agent-reviewer-feedback` | Reviewer requested changes on a PR (payload: chain_depth) | active |
| `azure-alert` | Azure Monitor alert fired via alert bridge function | external |
| `deploy-complete` | Deployment finished, triggers QA triage (deploy.yml → qa-triage.yml) | external |
| `dispute-detected` | Agent disagreement loop detected | stub |
| `pr-needs-review` | PR Manager flagged a PR for AI review (non-trivial risk) (payload: pr_number, risk_level, chain_depth) | external |

## Agent Schedules

| Agent | Schedule | Day | Event Triggers |
|-------|----------|-----|----------------|
| content-creator | `0 10 * * *` | daily | Manual |
| customer-ops | `0 */4 * * *` | daily | Manual |
| engineer | --- |  | Issues labeled/unlabeled, `agent-product-owner-complete`, `agent-reviewer-feedback`, PR closed, Check suite, Manual |
| escalation-lead | `0 18 * * 3` | Wed | `dispute-detected`, Manual |
| financial-analyst | `0 12 * * *` | daily | Manual |
| human-ops | `0 15 * * 5` | Fri | Manual |
| marketing-strategist | `0 8 * * 1` | Mon | Manual |
| ops-engineer | --- |  | Issues labeled/unlabeled, `agent-product-owner-complete`, Manual |
| product-analyst/market-intelligence | `0 3 * * 2,4` | Tue/Thu | Manual |
| product-analyst/product-discovery | `0 3 * * 1,3,5` | Mon/Wed/Fri | Manual |
| product-analyst/revenue-operations | --- |  | Manual |
| product-owner | `0 6,18 * * *` | daily | `agent-product-manager-feedback`, Manual |
| qa-analyst | `0 16 * * *` | daily | Manual |
| reviewer | `0 */12 * * *` | daily | `pr-needs-review`, Manual |
| site-reliability | `30 */4 * * *` | daily | `azure-alert`, Manual |
| strategic | `0 6 * * *` | daily | Manual |
| tech-lead/architecture-review | `0 7 * * *` | daily | Manual |
| tech-lead/doc-review | `0 16 * * *` | daily | Manual |
| tech-lead/full-scan | `0 9 * * *` | daily | Manual |
| tech-lead/harness-request-review | `0 14 * * *` | daily | Manual |
| tech-lead/infrastructure-review | `0 13 * * *` | daily | Manual |
| tech-lead/pipeline-quality-review | `0 20 * * *` | daily | Manual |
| tech-lead/project-structure-review | `0 19 * * *` | daily | Manual |
| tech-lead/qa-tooling-review | `0 15 * * *` | daily | Manual |
| tech-lead/security-scan | `0 11 * * *` | daily | Manual |
| tech-lead/tech-debt-scan | `0 8 * * *` | daily | Manual |
| tech-lead/test-review | `0 17 * * *` | daily | Manual |
| triage | `0 12 * * *` | daily | Issues opened, Manual |
| user-experience | --- |  | Manual |

## Safety Constraints

| Constraint | Value |
|------------|-------|
| `chain_depth_max` | 5 |
| `review_rounds_max` | 3 |
