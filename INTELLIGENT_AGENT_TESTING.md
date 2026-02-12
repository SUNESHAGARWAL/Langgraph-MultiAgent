# Intelligent Multi-Agent System - Testing Guide

**Version:** 5.2.0-intelligent-agents
**Date:** 2026-02-12
**Purpose:** Test autonomous LLM intelligence for column selection and business logic

---

## 🧠 What Makes This System INTELLIGENT?

### The Old Way (Hard-Coded Logic)
```python
# ❌ BAD: Hard-coded rules
if user_query == "sentiment":
    columns = ["sentiment_score", "city"]
    table = "pc_sales"
```

### The New Way (LLM Reasoning)
```
# ✅ GOOD: LLM reasons about what's needed
User: "show me sentiment"

Schema Analysis Agent thinks:
1. "Sentiment" could mean: sentiment_score, nps, satisfaction, feedback
2. Scans all tables for columns matching these concepts
3. Finds: pc_sales.sentiment_score, customer_feedback.nps_score
4. Asks user: "I found sentiment data in 2 tables - which one?"

User: "pc_sales, bangalore, october 2025"

Schema Analysis Agent thinks:
1. Table selected: pc_sales
2. Filter needed: city = bangalore
3. Date filter: date in October 2025
4. Additional context columns: product, category (for better insights)
5. Columns to use: sentiment_score, city, date, product

Query Planner Agent thinks:
1. User wants sentiment data with specific filters
2. Builds query: "From pc_sales, show sentiment_score where city is bangalore
   and date is in October 2025. Include product for context."
```

**Key Difference:** LLM REASONS about what's needed, not following hard-coded rules!

---

## 🎯 Test Case 1: Sentiment Analysis (Column Intelligence)

### User Input
```
🤔 You: show me sentiment
```

### Expected Intelligence Flow

**1. Schema Analysis Agent Reasoning:**
```
🧠 Agent thinks:
- User wants "sentiment" → What columns capture emotional/satisfaction data?
- Semantic matches: sentiment_score, nps, satisfaction, feedback_rating
- Scanning tables...
  ✓ Found: pc_sales.sentiment_score (product sentiment)
  ✓ Found: customer_feedback.nps_score (overall satisfaction)
- Multiple tables! Need to ask user which one.
- What filters are missing? Date range, location
```

**2. Clarification Response:**
```
🤖 System: I found sentiment data in 2 tables:

1. **pc_sales** - Contains sentiment_score for product-level sentiment analysis
2. **customer_feedback** - Contains nps_score for overall customer satisfaction

Which table would you like to analyze?

Also, please specify:
- Date range (e.g., "last month", "October 2025", "Q4 2024")
- Location filter (optional, e.g., "bangalore", "all regions")
```

**3. User Provides Details:**
```
🤔 You: pc_sales, bangalore, october 2025
```

**4. Schema Analysis Re-analyzes:**
```
🧠 Agent thinks:
- Table selected: pc_sales
- Filter columns needed:
  ✓ city (for bangalore filter)
  ✓ date (for October 2025 filter)
- Main metric: sentiment_score
- Context columns (helpful): product, category
- Selected columns:
  Required: sentiment_score, city, date
  Optional: product, category
```

**5. Query Planner Creates Smart Query:**
```
🧠 Agent thinks:
- Schema identified: sentiment_score, city, date, product
- Filters: city = bangalore, date in October 2025
- Build natural query for Genie...

QUERY:
"From the pc_sales table, show me the sentiment_score for records where
city is bangalore and date is in October 2025. Also include product and
category for additional context."
```

**6. Genie Executes → User Gets Answer**

### Key Intelligence Points
- ✅ **Semantic matching:** "sentiment" → sentiment_score, nps, satisfaction
- ✅ **Multiple table handling:** Detected 2 tables, asked user to choose
- ✅ **Column selection:** Identified city, date for filters + context columns
- ✅ **No hard-coding:** All decisions made by LLM reasoning

---

## 🎯 Test Case 2: Conversion Rate (Business Logic Understanding)

### User Input
```
🤔 You: what's our conversion rate?
```

### Expected Intelligence Flow

**1. Schema Analysis Agent Reasoning:**
```
🧠 Agent thinks:
- "Conversion rate" is a BUSINESS METRIC
- Formula: Conversion Rate = (Conversions / Total Visits) × 100
- What columns are needed?
  Option 1: Pre-calculated conversion_rate column (ideal)
  Option 2: Source columns to calculate (conversions, visits)
- Scanning tables for these columns...
  ✓ Found: web_analytics.conversion_count (numerator)
  ✓ Found: web_analytics.visitor_count (denominator)
  ✗ No pre-calculated conversion_rate column found
- Calculation needed: conversion_count / visitor_count
- Missing: date range (conversion rate for when?)
```

**2. Clarification Response:**
```
🤖 System: I can calculate the conversion rate for you!

BUSINESS LOGIC IDENTIFIED:
Conversion Rate = (conversion_count / visitor_count) × 100

COLUMNS FOUND in web_analytics table:
- conversion_count: Number of successful conversions
- visitor_count: Total number of visitors

SELECTED COLUMNS:
Required:
  - conversion_count (numerator for conversion rate calculation)
  - visitor_count (denominator for conversion rate calculation)
  - date (to filter time period)

Optional (for insights):
  - channel (traffic source: organic, paid, social)
  - device (desktop, mobile, tablet)

WHAT'S NEEDED:
Please specify the time period for conversion rate analysis:
- "last month"
- "Q4 2024"
- "October 2025"
- Or any specific date range

Would you also like to:
- Break down by channel? (see which traffic source converts best)
- Break down by device? (see mobile vs desktop conversion)
```

**3. User Provides Details:**
```
🤔 You: last quarter, show by channel
```

**4. Schema Analysis Confirms:**
```
🧠 Agent thinks:
- Time period: last quarter (Q4 2024)
- Breakdown requested: by channel
- Columns to use:
  Required: conversion_count, visitor_count, date, channel
  Calculation: conversion_count / visitor_count * 100
```

**5. Query Planner Creates Intelligent Query:**
```
🧠 Agent thinks:
- Business metric: conversion rate
- Formula: (conversions / visits) * 100
- Grouping: by channel
- Time filter: last quarter

QUERY:
"From the web_analytics table, calculate the conversion rate by dividing
conversion_count by visitor_count and multiplying by 100, for the last
quarter (Q4 2024). Group the results by channel to show conversion rates
for each traffic source (organic, paid, social, etc.)."

REASONING:
- Using conversion_count and visitor_count for calculation
- Filtering date to Q4 2024 (October-December 2024)
- Grouping by channel for breakdown analysis
- Calculating percentage (× 100) for readability
```

**6. Genie Executes Calculation → Returns Results**

### Key Intelligence Points
- ✅ **Business logic understanding:** Recognized conversion rate formula
- ✅ **Column identification:** Found conversion_count, visitor_count
- ✅ **Calculation planning:** Explained numerator/denominator to Genie
- ✅ **Context awareness:** Suggested channel/device breakdowns
- ✅ **Smart filtering:** Applied date range correctly
- ✅ **No hard-coding:** LLM reasoned about the business metric

---

## 🎯 Test Case 3: Complex Query (Multi-Column Reasoning)

### User Input
```
🤔 You: show me high-value customers
```

### Expected Intelligence Flow

**1. Schema Analysis Agent Reasoning:**
```
🧠 Agent thinks:
- "High-value customers" is ambiguous - what defines "high-value"?
- Common definitions:
  1. High total spend (lifetime value)
  2. Frequent purchasers (order count)
  3. High average order value
  4. Recent high-value purchases
- Need to determine which definition user wants
- Scanning for relevant columns...
  ✓ customer_id (to identify customers)
  ✓ total_revenue or lifetime_value (spending metric)
  ✓ order_count (frequency metric)
  ✓ avg_order_value (order size metric)
  ✓ last_purchase_date (recency metric)
  ✓ customer_segment (if pre-segmented)
```

**2. Clarification Response:**
```
🤖 System: I found customer data and can identify high-value customers!

WHAT DEFINES "HIGH-VALUE" FOR YOU?

Option 1: **Total Lifetime Value**
- Columns: customer_id, total_revenue, lifetime_value
- Definition: Customers with highest total spending
- Example: Top 10% by total revenue

Option 2: **Frequent Purchasers**
- Columns: customer_id, order_count, purchase_frequency
- Definition: Customers who buy most often
- Example: >10 orders in last 6 months

Option 3: **High Average Order Value**
- Columns: customer_id, avg_order_value
- Definition: Customers with largest average purchases
- Example: Average order >$500

Option 4: **RFM Combination** (Recency, Frequency, Monetary)
- Columns: last_purchase_date, order_count, total_revenue
- Definition: Recent, frequent, high-spending customers
- Example: Purchased in last 30 days + >5 orders + >$1000 spent

Which definition should I use? Or specify your own criteria (e.g., "customers who spent >$5000 last year")
```

**3. User Chooses:**
```
🤔 You: total lifetime value, top 10%
```

**4. Schema Analysis Confirms:**
```
🧠 Agent thinks:
- Definition: High lifetime value
- Metric: total_revenue or lifetime_value column
- Threshold: Top 10% (need to calculate percentile)
- Columns needed:
  Required: customer_id, total_revenue/lifetime_value
  Context: customer_name, email, join_date, last_purchase_date
```

**5. Query Planner Creates Query:**
```
QUERY:
"From the customers table, show me the top 10% of customers by total
lifetime value. Include customer_id, name, email, total_revenue, and
last_purchase_date. Sort by total_revenue descending."

REASONING:
- Identifying high-value as top 10% by total_revenue
- Selecting customer_id (identifier), total_revenue (metric)
- Including name, email for contact info
- Including last_purchase_date for recency context
- Sorting descending to show highest value first
```

### Key Intelligence Points
- ✅ **Ambiguity handling:** Recognized "high-value" has multiple meanings
- ✅ **Domain knowledge:** Knew common customer segmentation approaches
- ✅ **Column reasoning:** Identified revenue, frequency, recency columns
- ✅ **Context addition:** Included contact info for actionability
- ✅ **Smart clarification:** Gave user options instead of generic "what do you mean?"

---

## 🎯 Test Case 4: RAG-Enhanced Intelligence

### Setup: Create a Business Glossary Document
```bash
# Create business definitions document
cat > ./data/documents/business_glossary.md << 'EOF'
# Business Metrics Glossary

## NPS (Net Promoter Score)
- **Formula:** % Promoters (9-10) - % Detractors (0-6)
- **Column:** nps_score in customer_feedback table
- **Scale:** -100 to +100
- **Good Score:** >50 is excellent, 0-50 is good, <0 needs improvement

## CSAT (Customer Satisfaction Score)
- **Formula:** (Number of satisfied customers / Total responses) × 100
- **Column:** csat_rating in customer_feedback table
- **Scale:** 1-5 stars
- **Good Score:** >4.0 is excellent

## Conversion Rate
- **Formula:** (Conversions / Total Visitors) × 100
- **Our Definition:** conversion_count / visitor_count in web_analytics table
- **Benchmark:** 2-5% is typical for e-commerce

## Churn Rate
- **Formula:** (Customers Lost / Total Customers at Start) × 100
- **Columns:** churned_flag in customers table, or calculate from last_purchase_date
- **Our Definition:** No purchase in 90 days = churned
EOF
```

### User Input
```
🤔 You: what's our NPS?
```

### Expected Intelligence Flow (WITH RAG)

**1. RAG Agent Activates:**
```
🧠 RAG Agent thinks:
- User query: "what's our NPS"
- Search business glossary for "NPS"...
- Found definition!

RAG CONTEXT:
"NPS (Net Promoter Score)
- Formula: % Promoters (9-10) - % Detractors (0-6)
- Column: nps_score in customer_feedback table
- Scale: -100 to +100
- Good Score: >50 is excellent"
```

**2. Schema Analysis Agent Uses RAG Context:**
```
🧠 Agent thinks (with RAG context):
- User wants NPS
- RAG says: nps_score column in customer_feedback table
- RAG says: Scale is -100 to +100
- No need to ask which table - RAG told us!
- Missing: time period for NPS calculation

SELECTED COLUMNS:
- nps_score (main metric - RAG identified this)
- date (for time filtering)
- region (optional - for breakdown)
```

**3. Clarification (Minimal - RAG Helped!):**
```
🤖 System: I'll show you the NPS (Net Promoter Score) from the customer_feedback table.

BUSINESS CONTEXT (from documentation):
- NPS Formula: % Promoters (9-10) - % Detractors (0-6)
- Scale: -100 to +100
- Good Score: >50 is excellent

SELECTED COLUMNS:
- nps_score (Net Promoter Score metric)
- date (for time filtering)
- region (optional breakdown)

Please specify time period:
- "last month"
- "Q4 2024"
- "year to date"
- Or "all time" for overall NPS
```

**4. User Provides:**
```
🤔 You: last quarter
```

**5. Query Planner (RAG-Enhanced):**
```
QUERY:
"From the customer_feedback table, show me the NPS score for the last
quarter (Q4 2024). Calculate the average nps_score and also break it
down by region if available.

BUSINESS CONTEXT:
- NPS is on a scale of -100 to +100
- Scores above 50 are considered excellent
- This metric shows the percentage of promoters minus detractors"

REASONING:
- Using RAG-identified nps_score column
- Filtering to Q4 2024
- Including region breakdown for insights
- Genie will understand this is already calculated metric (not raw scores)
```

### Key Intelligence Points
- ✅ **RAG integration:** Used business glossary to identify column
- ✅ **No ambiguity:** RAG eliminated "which table?" question
- ✅ **Business context:** Shared NPS scale and benchmarks
- ✅ **Smarter queries:** Query includes business understanding

---

## 🎯 Test Case 5: Autonomous Column Selection

### User Input
```
🤔 You: compare sales performance across regions
```

### Expected Intelligence Flow

**1. Schema Analysis Agent Reasoning:**
```
🧠 Agent thinks:
- Goal: Compare sales performance across regions
- What's needed?
  1. Sales metric: revenue, sales_amount, order_value
  2. Geographic dimension: region, city, country
  3. Comparison requires: aggregation (sum, average)
  4. Context: time period for fair comparison

- Scanning tables...
  ✓ sales table found with: order_total, region, order_date
  ✓ Alternative: revenue_summary with: total_revenue, geography, period

- Which columns for comparison?
  Required:
    - revenue/sales metric
    - region/geography dimension
    - date (for time normalization)
  Optional:
    - order_count (volume vs value comparison)
    - product_category (drill-down capability)

- AUTONOMOUS DECISION:
  Table: sales (has all needed columns)
  Columns: order_total, region, order_date, order_count
  Aggregation: SUM(order_total), COUNT(orders) GROUP BY region
  Filter: Last 3 months (for recent performance)
```

**2. Minimal/No Clarification:**
```
🤖 System: I'll compare sales performance across regions using the sales table.

INTELLIGENT COLUMN SELECTION:
Required columns:
  - order_total (sales revenue metric)
  - region (geographic dimension for comparison)
  - order_date (time filter)

Additional context columns:
  - order_count (to see volume vs value)
  - avg_order_value (to understand basket size)

TIME PERIOD: Last 3 months (for recent performance comparison)

COMPARISON METRICS I'LL SHOW:
1. Total revenue by region
2. Order count by region
3. Average order value by region
4. Growth trend by region

Proceeding with analysis... (Say "wait" if you want different time period or columns)
```

**3. Query Planner (Autonomous):**
```
QUERY:
"From the sales table, compare performance across regions for the last 3 months.
Show total revenue (sum of order_total), order count, and average order value
for each region. Sort by total revenue descending to see top-performing regions."

REASONING:
- Autonomous column selection: order_total, region, order_date, order_count
- Comparison metrics: sum, count, average
- Time filter: last 3 months for recency
- Sorting: by revenue to highlight best performers
- No clarification needed - made smart assumptions
```

### Key Intelligence Points
- ✅ **Autonomous decision-making:** Chose columns without asking
- ✅ **Business logic:** Knew to aggregate and group for comparison
- ✅ **Reasonable defaults:** Last 3 months, sorted by revenue
- ✅ **Context addition:** Added order_count, avg_order_value for insights
- ✅ **Proactive:** Told user they can override if needed

---

## 🎯 Success Criteria

### The System is INTELLIGENT if:

1. **Semantic Column Matching**
   - ✅ "sentiment" finds sentiment_score, nps, satisfaction columns
   - ✅ "location" finds city, region, geography columns
   - ✅ "revenue" finds sales, amount, order_total columns

2. **Business Logic Understanding**
   - ✅ "conversion rate" identifies numerator/denominator columns
   - ✅ "churn rate" understands calculation formula
   - ✅ "high-value customers" suggests multiple definitions

3. **Autonomous Column Selection**
   - ✅ Selects minimal but sufficient columns
   - ✅ Adds context columns for better insights
   - ✅ Identifies required vs optional columns

4. **Smart Clarifications**
   - ✅ Asks specific questions, not "what do you want?"
   - ✅ Provides options when ambiguous
   - ✅ Makes autonomous decisions when possible

5. **RAG Integration**
   - ✅ Uses business glossary for definitions
   - ✅ Applies metric formulas from documentation
   - ✅ Understands column meanings from docs

6. **Context Awareness**
   - ✅ Suggests time filters when needed
   - ✅ Proposes breakdowns (by region, channel, etc.)
   - ✅ Adds drill-down capabilities

---

## 🚀 How to Run Tests

### 1. Enable RAG (for Test Case 4)
```bash
# .env
RAG_ENABLED=true

# Create business glossary
mkdir -p ./data/documents
# Add business glossary as shown above
```

### 2. Run the System
```bash
python -m src.main_simple
```

### 3. Test Each Case
Run through test cases 1-5 and verify:
- Schema analysis shows intelligent reasoning
- Column selection is smart, not hard-coded
- Business logic is understood
- RAG context enhances decisions
- Queries are specific and use identified columns

### 4. Check Logs
Look for:
```
=== Schema Analysis Agent ===
[Shows intelligent reasoning about columns]

=== Query Planner Agent ===
[Shows smart query with specific columns]
```

---

## 🎊 Summary

**This is NOT rule-based programming - this is LLM REASONING!**

The agents:
- ✅ **Think** about what columns are semantically relevant
- ✅ **Understand** business metrics and their calculations
- ✅ **Reason** about what data is needed
- ✅ **Select** minimal but sufficient columns
- ✅ **Use** RAG for business definitions
- ✅ **Make** autonomous decisions with smart defaults
- ✅ **Ask** intelligent questions only when truly needed

**The LLMs play the role of intelligent analysts, not code following hard-coded rules!**

Version: 5.2.0-intelligent-agents
Status: ✅ Production Ready for Intelligent Autonomous Operation
