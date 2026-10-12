# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Job seekers comparing openings, tracking applications, and preparing application material. The current user wants matching to adapt to their uploaded resume, including computer science and software roles.

## Product Purpose

Jobwatch collects openings from employer and listing sources, helps users find relevant jobs, and keeps applications and deadlines organized. Success means the user can trust the extracted resume facts, understand recommendations, and act on relevant openings quickly.

## Operating Context

A local Python service runs in the background on Windows and serves a browser interface. Existing workflows include Opportunities, Applications, Companies, Calendar, Analytics, Sources, and Settings. Users upload PDF, DOCX, or text resumes and review proposed profile changes.

## Capabilities and Constraints

- Resume extraction and deterministic parsing run locally.
- The current taxonomy, defaults, and many screen queries favor finance. The user has confirmed that the product should adapt to the uploaded resume, including software roles.
- Keep applications, resume data, explicit geography and authorization preferences, source settings, and update behavior intact.
- Retain the existing Python and browser JavaScript stack.
- Existing light and dark themes and keyboard navigation are part of the interface.
- No requirement for separate CS and finance profiles has been established.

## Brand Commitments

Keep the Jobwatch name. The user explicitly requested Impeccable and Emil Kowalski's design engineering principles to make the interface more modern and intuitive.

Visual direction (user's standing preference, 2026-10-12): a modern, professional, conventional work-tool look at the craft level of Linear and Height. No themed or conceptual worlds ("nothing this crazy"). Light and dark themes are equal citizens. Avoid the generic-SaaS template look (stock indigo accent, Inter, rounded cards everywhere). Keep the redesigned Opportunities layout and behavior.

## Product Principles

- Recommendations must follow supported resume evidence and user preferences.
- Explain inferred facts and allow review before applying profile changes.
- Prioritize finding, reviewing, and tracking relevant opportunities over collection statistics.
- Keep collection health transparent without overwhelming routine work.
- Preserve local operation and existing user data.
