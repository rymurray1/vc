# VC Database Project - Claude Code Guidelines

## Core Principles

This file documents important guidelines for this project to ensure consistency and efficiency.

## Web Scraping & Data Enrichment

### Always Use 6 Parallel Agents
**RULE: Always use exactly 6 parallel agents when performing any web scraping or data enrichment tasks.**

**Why:**
- 6 agents provides optimal parallelization without hitting rate limits
- Allows splitting work into equal batches
- Maintains good performance while respecting API/site rate limits
- Proven approach across multiple runs in this project

**How to apply:**
1. When scraping VC portfolios: Divide VCs into 6 batches, 1 agent per batch
2. When enriching companies with founder data: Split company list into 6 batches
3. When extracting data from any external source: Use 6-agent parallel approach

**Examples:**
- 24 VCs to scrape → 4 VCs per agent × 6 agents
- 282 companies to enrich → 47 companies per agent × 6 agents
- 100 companies to research → ~17 per agent × 6 agents

## Database Architecture

### File Structure
- `firms.json` - VC firm information with investment portfolios
- `founders.json` - Startup companies with founder/CEO/LinkedIn data
- `vc_tags.json` - VC metadata (focus areas, HQ, presence)

### Key Metrics to Track
- Total VCs: Currently 237
- Total Companies: Currently 5,262
- Coverage: Percentage with founder/CEO data (target: 95%+)

## Data Quality Standards

### Cleaning
- Remove entries with corrupted names (taglines, descriptions, etc.)
- Validate company name length (2-100 characters)
- Deduplicate across sources (case-insensitive for VCs)

### Enrichment
- Use Serper API for founder/CEO research (no rate limits)
- Capture: Founder names, CEO name, LinkedIn URLs
- Multi-strategy queries: ["[Company] founder CEO", "[Company] founder linkedin", etc.]

## Project Status

### Completed
✓ 237 VCs in database
✓ 5,262 startup companies
✓ 623 new companies from DBL Partners & Bessemer (in enrichment queue)
✓ Multiple portfolio sources scraped (Khosla, Lowercarbon, SHIFT Invest, etc.)
✓ Data cleanup pipeline established

### In Progress
→ Enriching 623 new companies from recent scrape (using 6 agents)
→ Additional energy VC portfolio scraping (16 remaining VCs)

## Future Scalability

When adding new data sources or VCs:
1. Identify sources
2. Batch into 6 parallel scraping tasks
3. Add to firms.json with investment portfolios
4. Add companies to founders.json
5. Batch companies into 6 parallel enrichment agents
6. Merge results and validate

## Important Notes

- **Never use fewer than 6 agents** for web scraping or enrichment tasks
- **Always save checkpoints** after each operation
- **Validate data** before and after bulk operations
- **Monitor coverage percentage** - aim for 95%+ with founder data
