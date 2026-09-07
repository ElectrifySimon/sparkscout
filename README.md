# Sparkscout MCP
 
Enable AI agents to access verified technical reports and global energy statistics with citations and structured data queries.
 
## What Is Sparkscout MCP?
 
Sparkscout MCP connects LLMs and AI agents to:
 
- Official energy and policy publications
- Historical energy statistics across countries and regions
- Public investment and financial flow datasets
- Citation-ready sources for generated responses
 
Instead of relying solely on model knowledge, agents can retrieve and reference authoritative data and reports directly.
 
## Key Capabilities
 
### Report Search & Retrieval
 
Search across publications and retrieve relevant content.
 
- Full-text BM25 search
- Report-level and chapter-level access
- Citation generation (APA-7 or raw format)
- Extracted passages with highlighted matches
 
### Statistical Data Access
 
Query structured datasets through a unified interface.
 
- Country and regional energy statistics
- Renewable energy indicators
- Public investment flows
- Aggregations and filtering
- Automatic ISO3 country mapping
 
### Citation Support
 
Responses can include source references such as:
 
```text
[reports: energy-transition-outlook-2025]
[data: country_capacity]
```
 
This helps users verify claims and trace information back to the original source.
 
---
 
## Quick Start
 
Add the following configuration to your MCP client.
 
### Configuration
 
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
 
### Supported Clients
 
- Claude Desktop
- Cursor
- AI Gateway
- Any MCP-compatible client
 
---
 
## Why Use Sparkscout?
 
| Standard LLM Workflow | With Sparkscout MCP |
|-----------------------|---------------------|
| May rely on memorized information | Uses verified underlying sources |
| Difficult to verify statistics | Access to 800,000+ historical data points |
| Generic policy summaries | Searches across official publications |
| Sources often missing | Built-in citations and traceability |
 
---
 
## Example Questions
 
### Policy + Data Analysis
 
> Compare Germany's solar capacity growth from 2015 to 2024 against [IGO]'s grid flexibility recommendations.
 
### Investment Analysis
 
> Which five countries received the highest public financial flows for wind energy in 2023?
 
### Regional Assessment
 
> What was the total off-grid solar capacity installed in Sub-Saharan Africa between 2018 and 2024?
 
### Publication Research
 
> What recommendations does [IGO] make regarding transmission expansion and grid modernization?
 
---
 
## Available Datasets
 
### Energy Capacity
 
#### `country_capacity`
 
Installed power capacity by country and technology.
 
- Unit: MW
- Coverage: 226 countries
- Technologies: 26
- Years: 2000-2025
 
#### `region_capacity`
 
Installed power capacity aggregated by world region.
 
- Unit: MW
- Coverage: 10 regions
- Technologies: 13
 
### Electricity Generation
 
#### `country_generation`
 
Electricity generation by country and technology.
 
- Unit: GWh
- Coverage: 224 countries
- Technologies: 21
- Years: 2000-2024
 
#### `region_generation`
 
Electricity generation by world region.
 
- Unit: GWh
- Coverage: 10 regions
- Technologies: 12
 
### Renewable Energy Indicators
 
#### `re_share`
 
Renewable energy share by country and region.
 
- Unit: %
- Coverage: 233 countries and regions
- Includes capacity and generation shares
 
### Heat Statistics
 
#### `heat_generation`
 
Heat generation by technology.
 
- Unit: TJ
- Coverage: 52 countries
- Technologies: 13
 
### Investment Data
 
#### `public_investments`
 
Public financial flows and investments.
 
- Unit: USD million (constant 2022 prices)
- Coverage: 201 countries
 
---
 
## Available Tools
 
### Reports
 
#### `sparkscout_search_reports`
 
Search report content using BM25 ranking.
 
**Use when:**
 
- Finding relevant publications
- Locating policy recommendations
- Discovering report excerpts
 
#### `sparkscout_get_report`
 
Retrieve complete reports or specific sections.
 
**Use when:**
 
- Reading source material
- Extracting chapter content
 
#### `sparkscout_list_reports`
 
Browse available reports and publication metadata.
 
#### `sparkscout_cite`
 
Generate formatted citations.
 
Supported formats:
 
- APA-7
- Raw frontmatter
 
---
 
### Datasets
 
#### `sparkscout_query_dataset`
 
Run filtered dataset queries.
 
#### `sparkscout_query_dataset_aggregations`
 
Perform grouped calculations:
 
- `SUM`
- `AVG`
- `MIN`
- `MAX`
- `COUNT`
 
#### `sparkscout_get_dataset_meta`
 
Inspect:
 
- Available fields
- Valid filter values
- Units
- Dataset schema
 
#### `sparkscout_get_dataset_value`
 
Retrieve a single metric or value.
 
#### `sparkscout_sample_dataset`
 
View sample records before querying.
 
#### `sparkscout_list_datasets`
 
List all available datasets and metadata.
 
---
 
### Smart Routing
 
#### `sparkscout_answer_question`
 
Unified entry point for natural-language questions.
 
The tool:
 
1. Searches relevant reports.
2. Identifies potential datasets.
3. Returns dataset hints for follow-up analysis.
 
Recommended for users who are unsure which reports or datasets to query directly.
 
---
 
## Typical Workflow
 
```text
User Question
↓
sparkscout_answer_question
↓
Relevant Reports Identified
↓
Suggested Datasets Returned
↓
Dataset Query & Aggregation
↓
Cited Answer Generated
```
 
---
 
## Features at a Glance
 
✅ Full-text search across technical reports
 
✅ Structured access to energy datasets
 
✅ Country and regional coverage
 
✅ Automatic ISO3 country code mapping
 
✅ Built-in citations
 
✅ Aggregation and analytical queries
 
✅ MCP-compatible architecture
 
✅ Optimized for AI agents and assistants
