# RAG Documents Directory

## Overview
This directory contains business documentation that enhances the RAG (Retrieval-Augmented Generation) system.

When the system receives a question, it searches these documents to:
1. **Understand terminology** - Learn what "sentiment," "NPS," "conversion" mean
2. **Find calculation formulas** - Know how to calculate metrics correctly
3. **Identify relevant columns** - Map business terms to database columns
4. **Apply business rules** - Follow company-specific logic and constraints

---

## Current Documents

### 1. data_dictionary.md
**Purpose:** Defines all database columns and their properties.

**Contains:**
- Column names and data types
- Valid value ranges
- Business context for each column
- Null handling rules
- Case sensitivity rules

**When to update:**
- New tables are added
- New columns are added
- Column definitions change
- Data validation rules change

### 2. metric_calculations.md
**Purpose:** Explains how to calculate business metrics.

**Contains:**
- Formulas for key metrics (NPS, CSAT, Conversion Rate, etc.)
- Required columns for each calculation
- Example SQL queries
- Interpretation guidelines
- Common pitfalls to avoid

**When to update:**
- New metrics are introduced
- Calculation methods change
- New business rules are added

### 3. business_glossary.md
**Purpose:** Defines business terms and concepts.

**Contains:**
- Definitions of business terms
- Common abbreviations
- Industry standards
- Time period definitions (Q1, Q2, etc.)
- Geographical classifications
- Red flags and best practices

**When to update:**
- New business terms are introduced
- Terminology changes
- New best practices emerge

---

## How to Add New Documents

### Supported File Formats
- ✅ **Markdown (.md)** - Recommended for text documentation
- ✅ **Text (.txt)** - Plain text files
- ✅ **PDF (.pdf)** - Scanned or digital documents
- ✅ **Word (.docx)** - Microsoft Word documents
- ✅ **JSON (.json)** - Structured data
- ✅ **CSV (.csv)** - Tabular data

### Adding a New Document

1. **Create the file** in this directory:
   ```bash
   touch data/documents/your_document.md
   ```

2. **Write clear, structured content:**
   ```markdown
   # Document Title

   ## Section 1: Topic
   Clear explanation with examples.

   ## Section 2: Another Topic
   More details...
   ```

3. **Rebuild the RAG index:**
   ```bash
   # Delete old index
   rm -rf data/vector_stores/rag_index

   # Run the system - it will automatically rebuild the index
   python -m src.main_simple
   ```

### Document Writing Best Practices

#### ✅ DO:
- **Use clear headings** - Make sections easy to find
- **Provide examples** - Show concrete use cases
- **Be specific** - "sentiment_score ranges from -1.0 to +1.0" not "sentiment is a score"
- **Include formulas** - Show exact calculations
- **Add context** - Explain why something matters
- **Use consistent terminology** - Match database column names
- **Organize logically** - Group related information

#### ❌ DON'T:
- Use vague language - "sometimes," "usually," "might"
- Skip examples - Abstract definitions without concrete cases
- Mix unrelated topics - Keep documents focused
- Use inconsistent terms - "city" vs "location" vs "region" for same thing
- Assume knowledge - Explain acronyms and jargon
- Write walls of text - Use bullets, tables, and formatting

---

## Document Ideas

### Business Domain Documents

**Product Catalog Documentation:**
```markdown
# Product Catalog

## Product Categories
- Electronics: Laptops, phones, tablets...
- Furniture: Desks, chairs, tables...

## Product Naming Conventions
- Format: Brand + Model + Variant
- Example: "Apple iPhone 15 Pro 256GB Blue"
```

**Customer Segmentation Guide:**
```markdown
# Customer Segments

## Premium Customers
- Definition: CLV > ₹50,000
- Characteristics: High AOV, low churn
- Special handling: Priority support

## Regular Customers
- Definition: CLV ₹10,000 - ₹50,000
...
```

**Seasonal Trends Documentation:**
```markdown
# Seasonal Patterns

## Diwali Season (October-November)
- Expected revenue: +40% vs normal months
- Top categories: Electronics, Home & Garden
- Regional variations: North > South

## Summer Sale (May-June)
...
```

### Technical Documentation

**Data Refresh Schedule:**
```markdown
# Data Refresh Cycles

## pc_sales table
- Refresh: Daily at 2 AM IST
- Lag: 24 hours
- Completeness: 99.5%

## web_analytics table
- Refresh: Hourly
- Lag: 1 hour
...
```

**Known Data Issues:**
```markdown
# Known Data Quality Issues

## Issue 1: Missing Cities
- **Problem:** Some records have NULL city
- **Affected:** ~5% of pc_sales records
- **Workaround:** Use location (region) instead
- **Fix ETA:** Q2 2025

## Issue 2: Duplicate Entries
...
```

**Table Relationships:**
```markdown
# Table Relationships

## Joining pc_sales with customer_feedback
```sql
SELECT
    s.customer_id,
    s.sale_amount,
    f.nps_score
FROM pc_sales s
LEFT JOIN customer_feedback f
    ON s.customer_id = f.customer_id
    AND DATE(s.date) = DATE(f.feedback_date)
```
```

### Process Documentation

**Escalation Procedures:**
```markdown
# Data Issue Escalation

## When Genie Returns Unexpected Results
1. Verify query syntax
2. Check data freshness
3. Validate filters applied
4. Contact: data-team@company.com

## When Metrics Don't Match Reports
...
```

**Business Logic Rules:**
```markdown
# Business Rules

## Discount Application Order
1. Apply category discount
2. Apply customer tier discount
3. Apply promotional discount
4. Calculate tax on final amount

## Revenue Recognition
- When: Order marked as "Delivered"
- Not before: Payment received
...
```

---

## Organizing Large Documentation

### Option 1: Subdirectories
```
data/documents/
├── metrics/
│   ├── ecommerce_metrics.md
│   ├── customer_metrics.md
│   └── financial_metrics.md
├── tables/
│   ├── pc_sales_schema.md
│   ├── web_analytics_schema.md
│   └── customer_feedback_schema.md
└── processes/
    ├── data_refresh.md
    └── escalation.md
```

**Note:** RAG system will search all subdirectories automatically.

### Option 2: Single Documents with Sections
```
data/documents/
├── comprehensive_metrics_guide.md (all metrics in one file)
├── complete_data_dictionary.md (all tables in one file)
└── business_processes.md (all processes in one file)
```

**Trade-off:** Easier to maintain but larger files.

---

## Testing Your Documentation

### 1. Add a New Document
Create a test document:
```bash
echo "# Test Document\n\nSample content for testing." > data/documents/test.md
```

### 2. Rebuild RAG Index
```bash
rm -rf data/vector_stores/rag_index
python -m src.main_simple
```

### 3. Use the Debug Notebook
Open `notebooks/debug_rag_system.ipynb` and run Section 3 to see if your document is retrievable.

### 4. Test with a Question
Ask a question that should match your new document:
```python
# In the notebook or CLI
"What is [term from your document]?"
```

---

## RAG Configuration

### Current Settings (from .env)
```bash
RAG_ENABLED=true                    # Enable/disable RAG
RAG_DOCUMENTS_PATH=./data/documents # Where documents are stored
RAG_TOP_K=3                         # Return top 3 similar documents
RAG_MIN_SIMILARITY=0.7              # Minimum similarity threshold
RAG_STANDALONE_THRESHOLD=0.85       # Answer directly if similarity > 0.85
```

### Tuning RAG Performance

**If RAG isn't finding relevant documents:**
- Lower `RAG_MIN_SIMILARITY` (e.g., 0.6 instead of 0.7)
- Add more specific documentation
- Use exact terminology from your questions

**If RAG returns too many irrelevant results:**
- Raise `RAG_MIN_SIMILARITY` (e.g., 0.8 instead of 0.7)
- Make documentation more focused
- Remove redundant documents

**If RAG answers are too superficial:**
- Increase `RAG_TOP_K` (e.g., 5 instead of 3)
- Add more detailed examples
- Include more context in documents

---

## Maintenance

### Regular Updates
- **Monthly:** Review and update metric definitions
- **Quarterly:** Add new seasonal patterns
- **After schema changes:** Update data dictionary immediately
- **After business rule changes:** Update business glossary

### Version Control
Consider tracking document versions:
```markdown
# Document Title
**Version:** 2.1
**Last Updated:** 2024-12-15
**Changes:** Added Q4 seasonal patterns

...content...
```

### Archival
Move outdated documents to an `archive/` subdirectory:
```bash
mkdir -p data/documents/archive
mv data/documents/old_doc.md data/documents/archive/
```

---

## Troubleshooting

### RAG Not Working
**Symptom:** System ignores RAG documents.

**Solutions:**
1. Check `RAG_ENABLED=true` in `.env`
2. Verify documents exist in `data/documents/`
3. Rebuild index: `rm -rf data/vector_stores/rag_index`
4. Check logs for RAG initialization errors

### Documents Not Found in Search
**Symptom:** Questions don't return expected documents.

**Solutions:**
1. Check similarity threshold (lower it temporarily)
2. Use exact terms from documents in questions
3. Add more specific keywords to documents
4. Check document file format is supported

### Slow RAG Performance
**Symptom:** Queries take too long.

**Solutions:**
1. Reduce `RAG_TOP_K` (fewer documents to search)
2. Use smaller documents (split large files)
3. Remove unused documents
4. Consider using faster embedding model

---

## Example: Adding a New Metric

Let's say you want to add "Cart Abandonment Rate" metric.

### Step 1: Add to metric_calculations.md
```markdown
### Cart Abandonment Rate
**Definition:** Percentage of shopping carts created but not converted to purchases.

**Formula:**
```
Cart Abandonment Rate = ((Carts Created - Purchases) / Carts Created) × 100
```

**Required Columns:**
- `cart_created_count`
- `purchase_count` or `conversion_count`

**Tables:**
- Primary: `web_analytics`

**Example Calculation:**
```sql
SELECT
    ((cart_created_count - purchase_count) * 100.0 / cart_created_count)
    as cart_abandonment_rate
FROM web_analytics
WHERE date >= '2024-10-01'
```

**Typical Range:** 60-80% for e-commerce
```

### Step 2: Add to business_glossary.md
```markdown
### Cart Abandonment Rate
- **Category:** E-commerce Metric
- **Definition:** Percentage of shoppers who add items to cart but don't complete purchase
- **Formula:** ((Carts - Purchases) / Carts) × 100
- **Industry Average:** 70%
- **When to Use:** Identify checkout process issues
```

### Step 3: Rebuild and Test
```bash
rm -rf data/vector_stores/rag_index
python -m src.main_simple
# Ask: "What is cart abandonment rate?"
```

---

## Getting Help

- **For RAG configuration:** Check `.env.example` and `src/core/config.py`
- **For debugging:** Use `notebooks/debug_rag_system.ipynb` Section 3
- **For vector store issues:** Delete `data/vector_stores/rag_index` and rebuild
- **For document format issues:** Check `src/utils/parsers.py` for supported formats

---

## Quick Reference

| Action | Command |
|--------|---------|
| Add document | Create file in `data/documents/` |
| Rebuild index | Delete `data/vector_stores/rag_index/` |
| Test RAG | Run Section 3 of debug notebook |
| Enable RAG | Set `RAG_ENABLED=true` in `.env` |
| Adjust sensitivity | Change `RAG_MIN_SIMILARITY` in `.env` |
| Get more results | Increase `RAG_TOP_K` in `.env` |

---

**Last Updated:** 2024-12-15
**Maintained By:** Data Team
