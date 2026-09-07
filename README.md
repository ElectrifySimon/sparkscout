# ⚡ Sparkscout MCP

> **Trusted energy intelligence for AI systems.**
>
> Sparkscout MCP enables AI assistants, analytical agents, and decision-support applications to access authoritative publications, structured energy statistics, and citation-ready evidence through a single Model Context Protocol (MCP) interface.

---

# 📋 Executive Summary

Sparkscout MCP bridges modern AI systems with trusted energy knowledge.

Rather than relying solely on model memory, AI agents can access curated publications and structured datasets to answer questions using verifiable evidence. This allows analysts, policymakers, researchers, developers, and decision-makers to generate insights that are transparent, reproducible, and grounded in authoritative sources.

Through a single MCP integration, Sparkscout provides access to:

✅ Official publications and technical reports

✅ More than 800,000 historical energy observations

✅ Country, regional, and global energy statistics

✅ Public finance and investment data

✅ Automated citations and source attribution

✅ Combined qualitative and quantitative analysis

Whether you are preparing a ministerial briefing, conducting policy analysis, building an AI assistant, or exploring energy transition trends, Sparkscout allows AI systems to move beyond plausible answers and toward evidence-based outputs.

---

# 🎯 Why Sparkscout?

Large language models are exceptionally good at synthesizing information.

Their limitation is not analysis. Their limitation is access to trusted, verifiable evidence.

Sparkscout addresses this challenge by connecting AI systems directly to curated publications and structured datasets through MCP.

| Conventional AI Workflow | Sparkscout Workflow |
|--------------------------|--------------------|
| Relies primarily on model memory | Grounded in authoritative sources |
| Difficult to verify statistics | Direct access to structured datasets |
| Limited traceability | Built-in citations |
| Publications and data exist in separate workflows | Unified analytical environment |
| Manual evidence gathering | Retrieval and analysis through a single interface |

For organisations operating in energy planning, policy development, investment analysis, research, and technical cooperation, this provides a stronger foundation for AI-assisted decision support.

---

# 🔎 What Your AI Agent Can Access

## 📚 Publications & Knowledge Retrieval

Search across technical reports, policy papers, flagship publications, analytical studies, and knowledge products.

Capabilities include:

- Full-text BM25 retrieval
- Section-level access
- Chapter-level extraction
- Report metadata exploration
- Citation generation
- Evidence retrieval for AI workflows

---

## 📊 Energy Statistics & Analytical Data

Access structured datasets covering:

- Renewable power capacity
- Electricity generation
- Renewable energy shares
- Heat generation
- Public financial flows
- Regional energy indicators

Datasets can be queried, filtered, aggregated, and combined through natural language interactions.

---

## 🔗 Source Attribution

Responses generated through Sparkscout can preserve references to supporting evidence.

Example:

```text
Germany's solar PV capacity more than doubled between 2015 and 2024.
[data: country_capacity]

Recent energy transition analyses emphasise that renewable deployment should be accompanied by investments in storage, flexibility, and grid infrastructure.
[reports: world-energy-transition-outlook]
```

This improves transparency and allows users to trace findings back to their source.

---

# 🚀 Getting Started

Add Sparkscout MCP to your MCP-compatible client.

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

## ✅ Supported Environments

- Claude Desktop
- Cursor
- Windsurf
- Microsoft Copilot Studio
- AI Gateway deployments
- Any MCP-compatible platform

---

# 💡 Example Questions

The true value of Sparkscout lies in combining evidence retrieval and statistical analysis in a single workflow.

---

## ⚡ Renewable Energy Deployment

> How has solar PV deployment evolved in Germany since 2015, and how does this compare with recommendations on grid flexibility and storage contained in recent energy transition reports?

**Combines**

- Publication retrieval
- Capacity statistics
- Citation generation

**Outputs**

- Historical solar deployment trends
- Capacity additions by year
- Relevant policy recommendations
- Supporting references

---

## 🔌 Grid Planning & System Integration

> Which regions have experienced the fastest growth in wind and solar capacity, and what transmission and flexibility measures are recommended to maintain system reliability?

**Combines**

- Regional capacity datasets
- Publication search
- Analytical synthesis

**Outputs**

- Regional growth comparisons
- Grid infrastructure implications
- System integration recommendations
- Source-backed evidence

---

## 🌍 Regional Energy Transition Assessment

> Compare renewable electricity generation growth across Southeast Asia between 2010 and 2024 and identify the technologies driving the largest increases.

**Combines**

- Generation datasets
- Technology-level analysis
- Trend identification

**Outputs**

- Regional growth trends
- Technology contributions
- Country highlights
- Supporting statistics

---

## 💰 Investment & Finance

> Which countries received the largest public financial flows for wind energy between 2020 and 2024, and how does investment compare to deployment outcomes?

**Combines**

- Public finance datasets
- Capacity statistics
- Cross-dataset analysis

**Outputs**

- Investment rankings
- Deployment outcomes
- Regional comparisons
- Evidence-based observations

---

## 🏝️ Energy Access

> How much off-grid solar capacity has been deployed across Sub-Saharan Africa since 2018, and what lessons emerge from recent publications on energy access strategies?

**Combines**

- Capacity datasets
- Regional analysis
- Publication retrieval

**Outputs**

- Deployment statistics
- Leading countries
- Policy insights
- Citation-ready references

---

## ⚙️ National Energy Transition Briefing

> Prepare an executive briefing on India's renewable energy transition covering capacity growth, electricity generation, renewable energy shares, and recent policy recommendations.

**Combines**

- Multiple datasets
- Publication search
- Automated summarisation

**Outputs**

- Executive summary
- Statistical profile
- Key transition trends
- Supporting citations

---

## 🌡️ Heat Sector Decarbonisation

> Evaluate renewable heat generation trends across Europe and identify technologies showing the strongest growth over the last decade.

**Combines**

- Heat generation datasets
- Trend analysis
- Comparative assessment

**Outputs**

- Technology trends
- Regional comparisons
- Long-term growth patterns
- Statistical evidence

---

## 🏛️ Ministerial & COP Briefings

> Prepare a briefing for energy ministers on power sector transformation, highlighting renewable deployment trends, investment flows, and recommendations from recent flagship publications.

**Combines**

- Publications
- Capacity statistics
- Generation statistics
- Investment data

**Outputs**

- Executive narrative
- Key evidence
- Strategic messages
- Full source attribution

---

# 🗄️ Available Datasets

Sparkscout provides access to curated statistical datasets through a unified analytical layer.

Country codes are automatically harmonised.

```text
DEU → Germany
BRA → Brazil
IND → India
EGY → Egypt
```

---

## ⚡ Power Capacity

### `country_capacity`

Installed power generation capacity by country and technology.

**Coverage**

- 226 countries
- 26 technologies
- 2000–2025

**Unit**

- MW

---

### `region_capacity`

Installed power generation capacity by world region.

**Coverage**

- 10 regions
- 13 technologies

**Unit**

- MW

---

## 🔌 Electricity Generation

### `country_generation`

Electricity generation by country and technology.

**Coverage**

- 224 countries
- 21 technologies
- 2000–2024

**Unit**

- GWh

---

### `region_generation`

Electricity generation by region.

**Coverage**

- 10 regions
- 12 technologies

**Unit**

- GWh

---

## ♻️ Renewable Energy Indicators

### `re_share`

Renewable energy share of total capacity and generation.

**Coverage**

- 233 countries and regions

**Unit**

- %

---

## 🌡️ Heat Statistics

### `heat_generation`

Heat generation by country and technology.

**Coverage**

- 52 countries
- 13 technologies

**Unit**

- TJ

---

## 💰 Public Finance

### `public_investments`

Public financial flows supporting energy technologies.

**Coverage**

- 201 countries

**Unit**

- USD million (constant 2022 prices)

---

# 🛠️ MCP Tools

Sparkscout exposes specialised MCP tools for knowledge retrieval, statistical analysis, and guided discovery.

---

## 📖 Publication Tools

### `sparkscout_search_reports`

Search across indexed publications and return the most relevant excerpts.

**Best for**

- Literature reviews
- Policy research
- Evidence gathering

---

### `sparkscout_get_report`

Retrieve complete reports or specific sections.

**Best for**

- Source review
- Chapter extraction
- Technical analysis

---

### `sparkscout_list_reports`

Browse available publications, years, metadata, and structures.

---

### `sparkscout_cite`

Generate publication citations.

Supported formats:

- APA 7
- Raw metadata

---

## 📊 Dataset Tools

### `sparkscout_query_dataset`

Execute filtered analytical queries against datasets.

---

### `sparkscout_query_dataset_aggregations`

Perform grouped calculations.

Supported functions:

```text
SUM
AVG
MIN
MAX
COUNT
```

---

### `sparkscout_get_dataset_meta`

Inspect:

- Columns
- Units
- Filters
- Dimensions
- Valid values

---

### `sparkscout_get_dataset_value`

Retrieve individual metrics or observations.

---

### `sparkscout_sample_dataset`

Explore representative records before querying.

---

### `sparkscout_list_datasets`

View dataset inventories, schemas, coverage periods, and metadata.

---

## 🧠 Intelligent Question Routing

### `sparkscout_answer_question`

Recommended starting point for most users.

The tool:

1. Interprets the question
2. Searches relevant publications
3. Identifies candidate datasets
4. Returns supporting evidence
5. Suggests analytical next steps

Ideal for exploratory analysis and first-pass research.

---

# 🔄 How Sparkscout Works

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

# 🎯 Typical Use Cases

## 🏛️ Policy Analysis

Assess how deployment trends align with recommendations contained in policy and technical publications.

---

## ⚙️ Energy Planning & Modelling

Support analyses of renewable deployment, power system evolution, resource adequacy, and long-term planning.

---

## 💵 Investment Analysis

Track public financial flows, compare investment trends, and assess deployment outcomes.

---

## 📑 Research & Technical Reporting

Accelerate evidence gathering, citation management, and analytical workflows.

---

## 🤖 AI Assistants & Knowledge Platforms

Equip organisational AI assistants with trusted energy-sector knowledge and verifiable sources.

---

## 🌐 International Cooperation

Support analytical work conducted by governments, development banks, international organisations, research institutions, and technical partners.

---

# ✅ Designed for Evidence

Sparkscout is built on a simple principle:

> The quality of AI-generated insight depends on the quality, transparency, and provenance of the information available to the model.

By combining publication retrieval, statistical analysis, and source attribution within a single MCP interface, Sparkscout enables AI systems to produce outputs that are not only useful, but also traceable, reproducible, and grounded in evidence.

For organisations working at the intersection of energy, policy, finance, technology, and international cooperation, Sparkscout provides a foundation for more trusted AI-enabled analytical workflows.
