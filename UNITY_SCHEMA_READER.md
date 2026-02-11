# Unity Catalog Schema Reader - Documentation

## Overview

The **UnitySchemaReader** reads your Unity Catalog tables, columns, types, and comments directly from Databricks using the Databricks SDK.

---

## What It Reads

### 1. **Configured Tables**

The system reads tables specified in your `.env` file:

```bash
UNITY_CATALOG_TABLES=catalog.schema.sales_table,catalog.schema.customer_table
```

**Format:** `catalog.schema.table` (three-level namespace)

---

### 2. **Table Metadata**

For each table, it reads:

```python
{
    "table_name": "catalog.schema.sales_table",
    "table_comment": "Sales transactions data with customer sentiment",
    "table_type": "TABLE",  # or "VIEW", "EXTERNAL", etc.
    "columns": [...]
}
```

**What's included:**
- Full table name
- Table comment/description (added when table was created)
- Table type (managed table, external table, view, etc.)

---

### 3. **Column Metadata**

For each column in the table:

```python
{
    "name": "sentiment_score",
    "type": "DOUBLE",
    "comment": "Customer sentiment score ranging from -1 (negative) to +1 (positive)",
    "nullable": true
}
```

**What's included:**
- Column name
- Data type (STRING, INT, DOUBLE, DATE, TIMESTAMP, etc.)
- Column comment/description
- Nullable flag

---

## How It Works

### Step 1: Initialize with Databricks Client

```python
workspace_client = WorkspaceClient(
    host=config.databricks.host,
    token=config.databricks.token,
)

schema_reader = UnitySchemaReader(workspace_client)
```

### Step 2: Read Schema for Each Table

```python
# For table: catalog.schema.sales_table
schema_info = schema_reader.read_table_schema("catalog.schema.sales_table")
```

### Step 3: Cache Results

Schema information is cached in memory to avoid repeated API calls:

```python
self.schema_cache[table_name] = schema_info
```

---

## Example: What Gets Read

### Your Unity Catalog Table Definition

```sql
CREATE TABLE catalog.schema.sales_table (
    transaction_id STRING COMMENT 'Unique transaction identifier',
    customer_id STRING COMMENT 'Customer ID from CRM system',
    product_name STRING COMMENT 'Name of product purchased',
    revenue DOUBLE COMMENT 'Transaction revenue in USD',
    city STRING COMMENT 'City where sale occurred',
    sentiment_score DOUBLE COMMENT 'Customer sentiment: -1 (negative) to +1 (positive)',
    transaction_date DATE COMMENT 'Date of transaction'
)
COMMENT 'Sales transactions with customer sentiment analysis';
```

### What the Schema Reader Extracts

```json
{
    "table_name": "catalog.schema.sales_table",
    "table_comment": "Sales transactions with customer sentiment analysis",
    "table_type": "TABLE",
    "columns": [
        {
            "name": "transaction_id",
            "type": "STRING",
            "comment": "Unique transaction identifier",
            "nullable": true
        },
        {
            "name": "customer_id",
            "type": "STRING",
            "comment": "Customer ID from CRM system",
            "nullable": true
        },
        {
            "name": "product_name",
            "type": "STRING",
            "comment": "Name of product purchased",
            "nullable": true
        },
        {
            "name": "revenue",
            "type": "DOUBLE",
            "comment": "Transaction revenue in USD",
            "nullable": true
        },
        {
            "name": "city",
            "type": "STRING",
            "comment": "City where sale occurred",
            "nullable": true
        },
        {
            "name": "sentiment_score",
            "type": "DOUBLE",
            "comment": "Customer sentiment: -1 (negative) to +1 (positive)",
            "nullable": true
        },
        {
            "name": "transaction_date",
            "type": "DATE",
            "comment": "Date of transaction",
            "nullable": true
        }
    ]
}
```

---

## How the Schema Is Used

### 1. **Question Analysis**

When you ask: *"What is sentiment for bangalore in sales?"*

The Schema Analysis Agent:
1. Sees `sales_table` has column `sentiment_score`
2. Sees `sales_table` has column `city` (for "bangalore")
3. Reads comments to understand what these columns mean
4. Determines: **Question is answerable!**

### 2. **Query Planning**

With schema knowledge, the Query Planner formats:

```
"From catalog.schema.sales_table,
 show sentiment_score
 where city = 'bangalore'"
```

Instead of sending messy chat history!

### 3. **Schema Summary for LLM**

The schema is formatted into a readable summary for the LLM:

```
Table: catalog.schema.sales_table
  Description: Sales transactions with customer sentiment analysis
  Columns (7):
    - transaction_id (STRING): Unique transaction identifier
    - customer_id (STRING): Customer ID from CRM system
    - product_name (STRING): Name of product purchased
    - revenue (DOUBLE): Transaction revenue in USD
    - city (STRING): City where sale occurred
    - sentiment_score (DOUBLE): Customer sentiment: -1 (negative) to +1 (positive)
    - transaction_date (DATE): Date of transaction
```

---

## Configuration

### Your .env File

```bash
# Unity Catalog Tables (comma-separated)
UNITY_CATALOG_TABLES=main.sales.transactions,main.sales.customers,main.sales.products

# Databricks Connection
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=dapi...
```

**Important:** Use the full three-level namespace:
- ✅ `catalog.schema.table`
- ❌ `schema.table` (will fail)
- ❌ `table` (will fail)

---

## Benefits

### ✅ **Understands Your Data**

Before:
- System blindly queries
- Doesn't know what columns exist
- Genie gets confused by ambiguous questions

After:
- System knows exactly what data you have
- Understands column meanings from comments
- Forms precise queries

### ✅ **Better Question Handling**

**Example 1:**
```
Question: "sentiment for bangalore"

Before: Routes to Genie with vague question
After: Checks schema → Finds sentiment_score and city → Formats clean query
```

**Example 2:**
```
Question: "show customer churn rate"

Before: Tries to query (fails if no churn_rate column)
After: Checks schema → No churn_rate column → Asks human how to calculate
```

### ✅ **Clean Query Formatting**

Because the system knows:
- Table names
- Column names
- Column types
- Column purposes (from comments)

It can format perfect queries:
```
"From main.sales.transactions,
 show sentiment_score, city, transaction_date
 where city = 'bangalore'
 and transaction_date >= '2025-11-01'"
```

---

## Troubleshooting

### Issue: "Failed to read schema for table"

**Cause:** Table doesn't exist or insufficient permissions

**Solution:**
1. Verify table exists in Unity Catalog
2. Check Databricks token has READ permissions
3. Verify table name format: `catalog.schema.table`

### Issue: "No comments" for all columns

**Cause:** Table was created without comments

**Solution:**
Add comments to your tables:

```sql
ALTER TABLE catalog.schema.sales_table
ALTER COLUMN sentiment_score
COMMENT 'Customer sentiment score from -1 to +1';
```

### Issue: Schema cache out of date

**Cause:** Table schema changed after system initialization

**Solution:**
Restart the system to reload schemas:

```bash
python -m src.main_clean
```

---

## Advanced: EDA (Future Enhancement)

### What Could Be Added

The schema reader could be extended to:

1. **Sample Data Analysis**
   ```python
   # Query sample rows
   sample_data = spark.sql(f"SELECT * FROM {table_name} LIMIT 100")

   # Analyze:
   - Data distributions
   - Null percentages
   - Value ranges
   - Common values
   ```

2. **Column Statistics**
   ```python
   # For numeric columns:
   - Min/max values
   - Mean, median
   - Standard deviation

   # For string columns:
   - Unique value count
   - Most common values
   - String length distribution
   ```

3. **Data Quality**
   ```python
   - Null rates per column
   - Duplicate row detection
   - Outlier identification
   - Referential integrity checks
   ```

4. **Relationships**
   ```python
   # Detect joins:
   - Foreign key patterns
   - Common column names across tables
   - Suggested joins
   ```

This would make the system even smarter about your data!

---

## Current Implementation

**What's Implemented:**
- ✅ Read table names
- ✅ Read table comments
- ✅ Read column names
- ✅ Read column types
- ✅ Read column comments
- ✅ Cache schemas
- ✅ Format for LLM analysis

**What's Not Yet Implemented (Future):**
- ⏳ Sample data analysis
- ⏳ Column statistics
- ⏳ Data quality checks
- ⏳ Relationship detection
- ⏳ Auto-suggest joins

---

## Summary

The **UnitySchemaReader** makes your multi-agent system **intelligent** by:

1. **Reading** Unity Catalog tables, columns, types, and comments
2. **Understanding** what data you have available
3. **Enabling** precise query planning
4. **Formatting** clean questions for Genie
5. **Validating** questions are answerable before querying

**Result:** No more sending messy chat history to Genie! The system knows your schema and sends clean, specific queries.

---

**Version:** 4.0.0-clean
**Status:** ✅ Production-Ready
**Next:** Run `python -m src.main_clean` to see it in action!
