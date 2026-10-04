# Temporary MVP discovery decision log

> **Status:** Working discovery record, not an MVP specification.
>
> **Location:** Local project file only. Do not move this document, its contents, or related notes to Obsidian without the user's explicit permission.
>
> This log records the decisions made in the problem/solution-definition interview. It is the durable reference for later MVP-spec writing; it does not authorize implementation.

## 1. Problem framing

### Primary user
Vietnamese university students and early-career candidates who are actively seeking an internship or job in an AI-related role.

### Core pain
Candidates need a clear, evidence-based picture of what Vietnamese employers state in AI-related job postings. Requirements are scattered across many job-posting sites and are difficult to read, query, normalize, count, chart, and compare manually. Candidates lack a big picture of which requirements recur across postings or change over time, so they prepare from fragmented and anecdotal examples rather than observed market signals.

### Consequence
Candidates may invest limited preparation time in skills, technologies, practical experience, portfolio evidence, or other preparation that does not align with the requirements most relevant to their target market and role.

### Primary moment of use
**Before applying.**

### Core question the MVP should answer
> Based on a defined collection of Vietnamese AI-related job postings, what requirements do employers commonly state for a selected role specialization, career level, and time range?

### Approved analysis questions and delivery scope
1. **Current requirement analysis — first release:** “For Junior AI/ML Engineer roles in Vietnam in the last 12 months, what requirements occur most often across skills, technologies, education, experience, English, and competencies? Show the frequency and job-posting evidence.”
2. **Career-level comparison — first release:** “How do requirements differ between AI/ML Engineer internships, junior roles, and senior roles in Vietnam? Show what appears at each level, not just one combined list.”
3. **Time-based trend comparison — later feature:** “Which requirements for Vietnam AI-related roles have changed most between the last 12 months and the previous 12 months? Show the chart, percentages, sample size, and supporting postings.”

## 2. V1 product definition

InternHunterAgent v1 is an **evidence-backed Vietnam AI job-market requirements analyzer**. It makes the requirements in collected job postings legible; it is not a general-purpose career chatbot.

### The MVP reports
- Requirements relating to skills, tools, technologies, capabilities, techniques, project/deliverable evidence, education, experience, English/language ability, and competencies.
- How frequently each requirement occurs in the selected dataset.
- Original job-posting evidence for each claim.
- Results filtered by role specialization, career level, and configurable time range.

### Evidence format
For every normalized requirement, show:
- number of matching postings;
- percentage of the filtered dataset;
- selected role specialization, career level, and time range;
- traceable supporting job-posting citations.

A citation should retain, when available:
- source site;
- original URL;
- job title;
- company;
- published date;
- relevant quoted job-description excerpt.

## 3. Target market, roles, and levels

### Market
Vietnam.

### Role boundary
Include the broad **AI-related job market**, using responsibility as the inclusion principle:

> A posting belongs in scope when its primary work involves building, applying, deploying, operating, evaluating, or managing AI/ML systems.

Relevant title families include, but are not limited to:
- AI Engineer / AI Developer;
- Machine Learning Engineer / AI-ML Engineer;
- Generative AI Engineer / LLM Engineer;
- NLP Engineer;
- Computer Vision Engineer;
- Inference Engineer;
- Applied AI Engineer;
- Data Science / Applied ML;
- MLOps / ML Platform;
- AI Research;
- AI Product / AI Management.

Original job titles must always be preserved. The role-specialization taxonomy is for filtering and aggregation, not a replacement for source wording. It must accommodate unfamiliar AI-related title variants.

### Career-level coverage
Include all levels:
- Intern;
- Entry-level / Junior;
- Mid-level;
- Senior;
- Lead / Manager;
- Unknown, when a title does not state a level clearly.

Internship and job requirements must not be silently combined. Results must identify the applicable career level, and later-level requirements must not be presented as prerequisites for internships.

### Career-level comparison presentation
The first version presents a **detailed, side-by-side comparison of two user-selected levels**. It does not require a full visual career-ladder view. A rich all-level career-ladder visualization is deferred.

### Career-level source of truth
The **original job title** is the source of truth for the displayed career-level label.

Rules:
1. Preserve the original title exactly.
2. Determine the level deterministically from title terms (for example, `Intern`, `Junior`, `Senior`, `Lead`, or `Manager`).
3. Extract stated years of experience as a separate requirement.
4. When title and stated experience appear inconsistent, show both; do not silently relabel the posting.

## 4. Time and data rules

### Time range
The analysis time window must be configurable.

- Use the original published posting date as the primary date truth.
- If the published date is unavailable, collection date may be used as a fallback and must be labeled clearly.
- Results must show their applied date range and the number of included postings.

The default date range remains undecided.

### Trend comparison
Trend analysis is a valuable **later feature**, not the product's core focus or first-release scope. Once stable historical data exists, it should compare two user-selected, equal-length periods and show:
- unique-posting counts and percentages for each period;
- a simple comparison chart;
- visible source coverage and sample sizes;
- grounded, non-causal descriptions of the displayed change.

Full monthly/quarterly time-series exploration is deferred until the dataset has sufficient stable history.

### Selected initial data-source strategy
Use a **source-controlled direct-employer cohort** as the initial strategy: Vietnam-relevant AI employers' direct career pages, documented ATS job feeds, and explicit written employer permission where needed. The product must identify this approved source cohort and report observations only within it; it must not claim nationwide job-market coverage.

This strategy is selected for stronger provenance, original citations, traceable posting metadata, lower vendor dependence, and a low technical-spend starting path. It still requires a separate approved research-led proposal/issue before collection or implementation begins.

### Future extension: scraper/data-provider pilot
A scraper/data provider such as Bright Data is **not** an initial data source. It may be evaluated later as a controlled, capped supplement only after target-source access, provider licence compatibility, retention/display rights, Vietnam data quality, and a fallback plan are approved. A free credit does not establish permission or production suitability.

Whatever source/collection approach is used, it must be permitted, traceable, and able to retain sufficient source text and metadata for citations.

## 5. Semantic normalization rules

Employer wording is heterogeneous. The system must preserve evidence while enabling useful aggregation.

### Three-layer representation
1. **Raw evidence:** the exact requirement wording/excerpt from the posting, never rewritten as source evidence.
2. **Normalized concept:** a canonical concept used for aggregation, such as `Conversational AI application development`.
3. **Requirement type:** the category used to present the concept honestly.

### Requirement types
- Tool/technology: Python, SQL, Docker, PyTorch, LangChain.
- Capability: LLM application development, model evaluation, API integration.
- Technique/concept: RAG, embeddings, fine-tuning, tool calling.
- Project/deliverable evidence: built a chatbot, deployed an AI system.
- Education requirement.
- Experience requirement.
- English/language requirement.
- Competency: communication, problem solving, teamwork, etc.

Projects/deliverables are a separate type; they must not be mislabeled as skills or technologies.

### Normalization safeguards
- Do not infer that semantically related phrases are identical without supporting context.
- For example, do not group a generic or rule-based chatbot with an LLM/RAG chatbot unless the source text supports that connection.
- Preserve the original expressions included in each aggregate.
- Ambiguous or unclassified expressions should remain visible for later review rather than being forced into an unsupported category.
- Build the taxonomy incrementally from real postings rather than inventing a large theoretical taxonomy first.

## 6. Explicitly deferred from the MVP

These may be future extensions, but are not part of the current MVP commitment:

- Personalized résumé upload, parsing, or skill-gap analysis.
- Judging whether an individual candidate is qualified/unqualified.
- Résumé rewriting or inventing résumé experience.
- Learning roadmaps.
- Suggested portfolio projects.
- General career advice not grounded in collected posting evidence.
- Broad web-wide answers outside the defined dataset.
- Making data-insufficiency handling a primary product focus.

## 7. Open questions for the continuing interview

1. Which permitted, reliable job-posting sources and acquisition method will supply the dataset?
2. What exact fields and quality checks are required at ingestion?
3. How will the role-specialization taxonomy classify AI-related titles, especially ambiguous titles?
4. Which normalized concepts and synonym mappings should be included first, and what review process handles ambiguity?
5. What is the first user workflow and result presentation: dashboard/filter view, conversational agent, report, or a combination?
6. What default time range, data-refresh cadence, and minimum dataset coverage are appropriate?
7. After inspecting a real-posting discovery sample, how do required, preferred, responsibility, and project/experience expressions actually appear, and which distinctions should the MVP support?
8. What evaluation criteria prove that extraction, normalization, frequencies, and citations are correct?

## 8. Related temporary note

`TEMP_AI_AGENT_LEARNING_ROADMAP.md` remains a separate local learning note. It has not been moved, modified, or converted into this discovery record.
