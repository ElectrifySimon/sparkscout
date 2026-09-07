# ⚡ Sparkscout MCP

Give your AI agent instant, verifiable access to official technical reports and global energy data.

---

## 🚀 30-Second Setup

Add this configuration block to your MCP client (`claude_desktop_config.json`, Cursor, or AI Gateway):

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

---

## 🎯 What Your AI Agent Gains

| Without Sparkscout MCP | With Sparkscout MCP |
| --- | --- |
| **Hallucinated stats** | Grounded in 800,000+ verified historical data points from a reputable IGO.
|
| **Vague policy summaries** | BM25 full-text search across official IRENA publications.
|
| **Unverifiable claims** | Automatic citation markers (`[reports: ...]` & `[data: ...]`) in outputs.
|

---

## 💬 Prompts to Try

Once connected, ask your LLM questions like these:

> **Policy & Data Synthesis**
> *"Compare Germany's solar capacity growth from 2015–2024 against IRENA's grid flexibility recommendations."*

> **Financial & Investment Tracking**
> *"Which 5 countries received the highest public financial flows for wind energy in 2023?"*
> 

> **Regional Capacity Deep-Dives**
> *"What was the total off-grid solar capacity installed in Sub-Saharan Africa between 2018 and 2024?"*

---

## 📊 Available Statistical Datasets

Your agent queries DuckDB under the hood with automatic ISO3 country code mapping (e.g., `DEU` automatically resolves to `Germany`):

| Dataset ID | What's Inside | Metrics | Coverage |
| --- | --- | --- | --- |
| `country_capacity`<br> | Country Power Capacity

 | **MW**<br> | 226 Countries • 26 Technologies • 2000–2025

 |
| `country_generation`<br> | Electricity Generation

 | **GWh**<br> | 224 Countries • 21 Technologies • 2000–2024

 |
| `region_capacity`<br> | Regional Power Capacity

 | **MW**<br> | 10 World Regions • 13 Technologies

 |
| `region_generation`<br> | Regional Generation

 | **GWh**<br> | 10 World Regions • 12 Technologies

 |
| `re_share`<br> | Renewable Energy Share

 | **%**<br> | 233 Countries/Regions • Capacity vs Gen

 |
| `heat_generation`<br> | Heat Generation Stats

 | **TJ**<br> | 52 Countries • 13 Technologies

 |
| `public_investments`<br> | Public Financial Flows

 | **USD M**<br> | 201 Countries • 2022 Constant Prices

 |

---

## 🛠️ Tool Cheat Sheet (11 Tools)

### 📖 Reports (Qualitative Search)

* **`irena_search_reports`**: BM25-ranked full-text search returning relevant excerpts with highlighted query terms.


* **`irena_get_report`**: Fetch complete report markdown or specific H2 chapters.


* **`irena_list_reports`**: See available reports, publication years, and section structures.


* **`irena_cite`**: Generate standardized APA-7 or raw frontmatter citations.



### 📈 Datasets (Quantitative Queries)

* **`irena_query_dataset`**: Filtered SQL queries with auto-translated codes and labels.


* **`irena_query_dataset_aggregations`**: Compute `SUM`, `AVG`, `MIN`, `MAX`, or `COUNT` groupings.


* **`irena_get_dataset_meta`**: Inspect columns, valid filter options, and metric units.


* **`irena_get_dataset_value`**: Quick lookup for a single metric or small key-value pair.


* **`irena_sample_dataset`**: Inspect random sample rows to understand table structures.


* **`irena_list_datasets`**: Quick inventory of table IDs, schemas, and time horizons.



### 🔀 Smart Router

* **`irena_answer_question`**: Single-shot tool that searches reports and generates target `DatasetHint[]` candidates for follow-up statistical queries.
