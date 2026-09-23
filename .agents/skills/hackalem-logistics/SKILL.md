---
name: hackalem-logistics
description: Analyze a newly released HackAlem logistics case, extract its exact requirements, and shape a feasible agentic AI MVP for a five-hour build. Use only after the official case text or files are available.
---

# HackAlem Logistics

## Start from the case

Read the complete official case, attachments, provided data, judging criteria, and submission fields before choosing an idea. Produce a requirement table with the source passage, whether it is mandatory, the evidence needed in the demo, and remaining ambiguity. Do not fill gaps with assumed logistics rules.

Select one operational disruption or decision that the provided data can support. Prefer a flow where the agent gathers evidence, calls small tools, compares feasible options, and asks a human to approve the proposed action.

## Design the MVP

Map the case as:

`event → evidence → constraints → deterministic calculation → options → recommendation → human approval → recorded result`

Use code for quantities, capacity, time windows, distance matrices, costs, SLA checks, and rankings. Use the model to extract facts, choose tools, connect evidence, explain trade-offs, and draft a proposed action. Label assumptions and missing values. Never invent coordinates, tariffs, travel times, capacities, availability, savings, or completed actions.

Choose the smallest working flow that satisfies every mandatory requirement. Useful patterns only when supported by the case include disruption recovery, document discrepancy review, dock scheduling, capacity allocation, shipment exception triage, and route comparison. Do not force route optimization when the case is about documents or communication.

## Five-hour boundary

Prioritize the end-to-end path, reproducible calculations, readable evidence, failure handling, README, and submission. Defer integrations, maps, authentication, databases, and optimization engines unless the official case requires them or they directly improve the judged scenario.

Before implementation, define acceptance checks and a 60–90 second demo with exact inputs and expected outputs. Before submission, run that path three times, verify every displayed number from source data, scan for secrets, and distinguish proposed actions from executed actions.

## Output

Return: requirements table, chosen user and decision, input/output contract, tool list, calculation rules, UI sequence, role split for the team, timed build plan, verification steps, demo script, limitations, and unresolved questions.
