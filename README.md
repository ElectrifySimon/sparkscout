# ⚡ Sparkscout MCP

> Trusted energy intelligence for AI systems.
>
> Sparkscout MCP enables AI assistants, analytical agents, and decision-support applications to access official publications, authoritative statistics, and citation-ready evidence through a single Model Context Protocol (MCP) interface.

---

# Executive Summary

Sparkscout MCP bridges large language models with curated energy knowledge resources.

It allows AI systems to combine narrative evidence from publications with structured statistical analysis, producing outputs that are transparent, traceable, and grounded in authoritative sources.

Through a single MCP integration, AI applications can:

- Search and retrieve content from official energy publications
- Access more than 800,000 verified statistical observations
- Query country, regional, and global energy datasets
- Generate source-attributed responses
- Combine qualitative findings with quantitative evidence

Sparkscout is designed for policy analysis, energy planning, investment assessment, research support, and AI-enabled knowledge services where credibility and verifiability matter.

---

# Why Sparkscout?

The challenge facing many AI-enabled analytical workflows is not generating answers. It is establishing confidence in those answers.

While foundation models can synthesize information effectively, they cannot independently verify the provenance of statistics, recommendations, or policy conclusions. For organisations operating in the energy sector, this creates limitations around transparency, reproducibility, and institutional trust.

Sparkscout addresses this challenge by connecting AI systems directly to curated energy datasets and official publications.

| Conventional AI Workflow | Sparkscout-Enabled Workflow |
|--------------------------|-----------------------------|
| Relies primarily on model memory | Accesses authoritative source material |
| Limited traceability of evidence | Source-linked responses |
| Difficult to validate statistics | Direct access to structured datasets |
| Separate workflows for reports and data | Unified analytical environment |
| Manual citation processes | Automated source attribution |

The result is an AI workflow that is better aligned with the standards expected by governments, international organisations, development institutions, researchers, and energy-sector decision makers.

---

# Core Capabilities

## Knowledge Retrieval

Search across a growing collection of energy publications, technical reports, analytical studies, and policy documents.

Capabilities include:

- Full-text semantic and BM25 retrieval
- Section- and chapter-level access
- Publication metadata discovery
- Citation generation
- Retrieval of supporting evidence for AI outputs

---

## Statistical Intelligence

Access structured datasets covering:

- Renewable power capacity
- Electricity generation
- Renewable energy shares
- Heat generation
- Public financial flows
- Regional energy indicators

Data can be filtered, aggregated, and analysed through natural language interactions.

---

## Evidence-Based Responses

Sparkscout enables AI systems to produce responses supported by identifiable sources.

Example:

```text
Solar photovoltaic capacity in Germany increased substantially between 2015 and 2024.
[data: country_capacity]

Grid expansion should be accompanied by investments in flexibility resources and system integration measures.
[reports: world-energy-transition-outlook]
```

This provides transparency for users while maintaining the analytical strengths of large language models.

---

# Typical Applications

### Energy Planning and Modelling

Support assessments of generation capacity, renewable deployment trends, electrification pathways, and regional energy transitions.

### Policy and Regulatory Analysis

Connect policy recommendations from official publications with relevant supporting data.

### Investment and Market Intelligence

Analyse technology deployment, public financial flows, and long-term energy investment trends.

### Research and Knowledge Services

Accelerate literature reviews, evidence gathering, and citation management.

### AI Copilots and Digital Assistants

Equip institutional AI assistants with trusted energy-sector knowledge and verifiable sources.

---

# Getting Started

Add the following configuration to your MCP-compatible client.

```json
{
  "mcpServers": {
    "sparkscout": {
      "url": "https://<your-mcp-endpoint>/fastmcp",
      "headers": {
        "Authorization": "Bearer <YOUR_BEARER_TOKEN>"
      }
    }
  }
}
```

Supported environments include:

- Claude Desktop
- Cursor
- Microsoft Copilot Studio
- AI Gateway deployments
- MCP-compatible enterprise assistants

---

# Example Analytical Questions

### Energy Transition Assessment

> Compare solar capacity growth in Germany between 2015 and 2024 with recommendations on grid flexibility contained in recent energy transition publications.

### Public Finance Analysis

> Identify the countries receiving the highest levels of public investment for wind energy deployment in 2023.

### Regional Infrastructure Planning

> Quantify off-grid solar deployment in Sub-Saharan Africa between 2018 and 2024 and summarise key regional trends.

### Evidence Review

> Summarise recommendations related to transmission planning across recent flagship publications.

### Executive Briefing

> Prepare a short briefing on renewable energy deployment in Southeast Asia using recent statistics and supporting references.

---

# Statistical Datasets

Sparkscout provides access to curated energy statistics through a unified query layer.

Country identifiers are automatically harmonised.

```text
DEU → Germany
BRA → Brazil
IND → India
```

## Power Capacity

### `country_capacity`

Installed power generation capacity by country and technology.

**Coverage**

- 226 countries
- 26 technologies
- 2000–2025

**Unit:** MW

### `region_capacity`

Installed power generation capacity by world region.

**Coverage**

- 10 regions
- 13 technologies

**Unit:** MW

---

## Electricity Generation

### `country_generation`

Electricity generation by country and technology.

**Coverage**

- 224 countries
- 21 technologies
- 2000–2024

**Unit:** GWh

### `region_generation`

Electricity generation by region.

**Coverage**

- 10 regions
- 12 technologies

**Unit:** GWh

---

## Renewable Energy Indicators

### `re_share`

Renewable energy shares based on installed capacity and electricity generation.

**Coverage**

- 233 countries and regions

**Unit:** %

---

## Heat Statistics

### `heat_generation`

Heat generation by technology and country.

**Coverage**

- 52 countries
- 13 technologies

**Unit:** TJ

---

## Public Finance

### `public_investments`

Public financial flows supporting energy technologies.

**Coverage**

- 201 countries

**Unit:** USD million (constant 2022 prices)

---

# MCP Tools

Sparkscout exposes specialised tools for both document retrieval and statistical analysis.

## Publications

### `sparkscout_search_reports`

Search across publication content and retrieve the most relevant excerpts.

### `sparkscout_get_report`

Access complete publications or individual sections.

### `sparkscout_list_reports`

Browse available reports and publication metadata.

### `sparkscout_cite`

Generate publication citations in standard formats.

---

## Datasets

### `sparkscout_query_dataset`

Execute filtered dataset queries.

### `sparkscout_query_dataset_aggregations`

Perform grouped calculations and aggregations.

Supported functions:

```text
SUM
AVG
MIN
MAX
COUNT
```

### `sparkscout_get_dataset_meta`

Inspect schemas, variables, dimensions, and units.

### `sparkscout_get_dataset_value`

Retrieve individual metrics.

### `sparkscout_sample_dataset`

Explore representative sample records.

### `sparkscout_list_datasets`

View available datasets and coverage information.

---

## Guided Question Answering

### `sparkscout_answer_question`

A high-level orchestration tool that:

1. Interprets the user's question
2. Identifies relevant publications
3. Suggests applicable datasets
4. Provides supporting evidence for further analysis

For most analytical workflows, this is the recommended entry point.

---

# Analytical Workflow

```text
Policy Question
        │
        ▼
Publication Discovery
        │
        ▼
Evidence Retrieval
        │
        ▼
Dataset Identification
        │
        ▼
Statistical Analysis
        │
        ▼
Source-Attributed Insight
```

---

# Designed for Evidence

Sparkscout reflects a simple principle:

> Analytical quality depends not only on the sophistication of the model, but on the quality, transparency, and provenance of the information available to it.

By integrating publications, statistical datasets, and source attribution within a single MCP interface, Sparkscout supports AI-enabled workflows that meet the expectations of governments, international organisations, research institutions, development partners, and energy-sector practitioners.
