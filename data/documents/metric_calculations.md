# Business Metric Calculations

## Overview
This document defines how to calculate key business metrics from available data.

---

## E-Commerce Metrics

### Conversion Rate
**Definition:** Percentage of visitors who complete a purchase.

**Formula:**
```
Conversion Rate = (Conversions / Total Visitors) × 100
```

**Required Columns:**
- `conversion_count` or `conversions` or `purchases`
- `visitor_count` or `visitors` or `total_visitors`

**Tables:**
- Primary: `web_analytics`

**Example Calculation:**
```sql
-- If pre-calculated column exists
SELECT conversion_rate FROM web_analytics

-- If needs to be calculated
SELECT
    (conversion_count * 100.0 / visitor_count) as conversion_rate
FROM web_analytics
WHERE date >= '2024-10-01' AND date <= '2024-12-31'
```

**Typical Range:** 1% to 5% for most e-commerce sites

---

### Average Order Value (AOV)
**Definition:** Average amount spent per order.

**Formula:**
```
AOV = Total Revenue / Number of Orders
```

**Required Columns:**
- `total_revenue` or `sale_amount` (summed)
- `order_count` or count of orders

**Tables:**
- Primary: `pc_sales`

**Example Calculation:**
```sql
SELECT
    SUM(sale_amount) / COUNT(DISTINCT order_id) as avg_order_value
FROM pc_sales
WHERE date >= '2024-10-01'
```

**Business Context:** Higher AOV indicates customers are buying more expensive items or multiple items per order.

---

## Customer Satisfaction Metrics

### Net Promoter Score (NPS)
**Definition:** Measures customer loyalty and likelihood to recommend.

**Formula:**
```
NPS = % Promoters - % Detractors
```

**Categories:**
- **Promoters:** Score 9-10
- **Passives:** Score 7-8
- **Detractors:** Score 0-6

**Required Columns:**
- `nps_score` (0-10 scale)

**Tables:**
- Primary: `customer_feedback`

**Example Calculation:**
```sql
SELECT
    (SUM(CASE WHEN nps_score >= 9 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) -
    (SUM(CASE WHEN nps_score <= 6 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as nps
FROM customer_feedback
WHERE feedback_date >= '2024-01-01'
```

**Interpretation:**
- NPS > 50: Excellent
- NPS 30-50: Good
- NPS 0-30: Needs improvement
- NPS < 0: Critical issues

---

### Customer Satisfaction Score (CSAT)
**Definition:** Immediate satisfaction after interaction.

**Formula:**
```
CSAT = (Number of Satisfied Customers / Total Responses) × 100
```

**Satisfied = Score 4 or 5 on 1-5 scale**

**Required Columns:**
- `csat_score` (1-5 scale)

**Tables:**
- Primary: `customer_feedback`

**Example Calculation:**
```sql
SELECT
    (SUM(CASE WHEN csat_score >= 4 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as csat_percentage
FROM customer_feedback
WHERE csat_score IS NOT NULL
```

**Typical Range:** 70-85% for healthy businesses

---

### Average Sentiment Score
**Definition:** Overall customer sentiment from transactions.

**Formula:**
```
Avg Sentiment = SUM(sentiment_score) / COUNT(records)
```

**Required Columns:**
- `sentiment_score` (-1.0 to +1.0 scale)

**Tables:**
- Primary: `pc_sales`

**Example Calculation:**
```sql
SELECT
    AVG(sentiment_score) as avg_sentiment,
    COUNT(*) as total_records
FROM pc_sales
WHERE city = 'bangalore'
  AND date >= '2024-10-01'
```

**Interpretation:**
- +0.5 to +1.0: Very positive
- +0.2 to +0.5: Positive
- -0.2 to +0.2: Neutral
- -0.5 to -0.2: Negative
- -1.0 to -0.5: Very negative

---

## Growth & Trend Metrics

### Year-over-Year (YoY) Growth
**Definition:** Percentage change compared to same period last year.

**Formula:**
```
YoY Growth = ((Current Period - Prior Period) / Prior Period) × 100
```

**Example Calculation:**
```sql
WITH current_year AS (
    SELECT SUM(sale_amount) as revenue
    FROM pc_sales
    WHERE date >= '2024-01-01' AND date <= '2024-12-31'
),
prior_year AS (
    SELECT SUM(sale_amount) as revenue
    FROM pc_sales
    WHERE date >= '2023-01-01' AND date <= '2023-12-31'
)
SELECT
    ((current_year.revenue - prior_year.revenue) * 100.0 / prior_year.revenue) as yoy_growth
FROM current_year, prior_year
```

---

### Month-over-Month (MoM) Growth
**Definition:** Percentage change compared to previous month.

**Formula:**
```
MoM Growth = ((This Month - Last Month) / Last Month) × 100
```

**Example Calculation:**
```sql
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', date) as month,
        SUM(sale_amount) as revenue
    FROM pc_sales
    GROUP BY DATE_TRUNC('month', date)
)
SELECT
    month,
    revenue,
    ((revenue - LAG(revenue) OVER (ORDER BY month)) * 100.0 /
     LAG(revenue) OVER (ORDER BY month)) as mom_growth
FROM monthly_revenue
```

---

## Customer Lifetime Value (CLV)

### Simple CLV
**Definition:** Average revenue per customer over their lifetime.

**Formula:**
```
CLV = Average Order Value × Purchase Frequency × Customer Lifespan
```

**Simplified Formula:**
```
CLV = Total Revenue from Customer / Total Customers
```

**Required Columns:**
- `sale_amount`
- `customer_id`

**Tables:**
- Primary: `pc_sales`

**Example Calculation:**
```sql
SELECT
    customer_id,
    SUM(sale_amount) as customer_lifetime_value,
    COUNT(DISTINCT order_id) as total_purchases,
    AVG(sale_amount) as avg_purchase_value
FROM pc_sales
WHERE customer_id IS NOT NULL
GROUP BY customer_id
```

---

## Churn Metrics

### Churn Rate
**Definition:** Percentage of customers who stopped purchasing.

**Formula:**
```
Churn Rate = (Customers Lost / Total Customers at Start) × 100
```

**Required Columns:**
- `customer_id`
- `date` or `last_purchase_date`

**Tables:**
- Primary: `pc_sales`

**Example Calculation:**
```sql
WITH customer_activity AS (
    SELECT
        customer_id,
        MAX(date) as last_purchase_date
    FROM pc_sales
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
)
SELECT
    COUNT(CASE WHEN last_purchase_date < CURRENT_DATE - INTERVAL '90 days' THEN 1 END) * 100.0 /
    COUNT(*) as churn_rate_90_days
FROM customer_activity
```

**Threshold:** Customers with no purchase in 90 days = churned

---

## Regional Performance Metrics

### Regional Sentiment Comparison
**Definition:** Compare average sentiment across different cities/regions.

**Required Columns:**
- `sentiment_score`
- `city` or `location`

**Tables:**
- Primary: `pc_sales`

**Example Calculation:**
```sql
SELECT
    city,
    AVG(sentiment_score) as avg_sentiment,
    COUNT(*) as sample_size,
    MIN(sentiment_score) as min_sentiment,
    MAX(sentiment_score) as max_sentiment
FROM pc_sales
WHERE city IS NOT NULL
GROUP BY city
ORDER BY avg_sentiment DESC
```

**Business Insight:** Identifies cities with customer satisfaction issues.

---

### Revenue by Region
**Definition:** Total revenue generated per city/region.

**Required Columns:**
- `sale_amount`
- `city` or `location`

**Tables:**
- Primary: `pc_sales`

**Example Calculation:**
```sql
SELECT
    city,
    SUM(sale_amount) as total_revenue,
    COUNT(*) as total_orders,
    AVG(sale_amount) as avg_order_value
FROM pc_sales
WHERE city IS NOT NULL
  AND date >= '2024-01-01'
GROUP BY city
ORDER BY total_revenue DESC
```

---

## Important Calculation Rules

### Date Filtering
1. **Always use explicit date ranges** - Never assume "current" period
2. **Quarter Definitions:**
   - Q1: January 1 - March 31
   - Q2: April 1 - June 30
   - Q3: July 1 - September 30
   - Q4: October 1 - December 31

3. **Month References:**
   - "Last month" = Previous calendar month
   - "This month" = Current calendar month
   - "Last 30 days" = Exactly 30 days from today

### Location Filtering
1. **Never assume default city** - Always require explicit city filter when asked
2. **Case-insensitive matching** - Use LOWER() or UPPER() for comparisons
3. **NULL handling** - Decide whether to include/exclude NULL cities

### Aggregations
1. **COUNT(*) vs COUNT(column):**
   - COUNT(*): Counts all rows including NULLs
   - COUNT(column): Counts only non-NULL values

2. **AVG() excludes NULLs automatically**
3. **SUM() returns NULL if all values are NULL**

### Null Safety
```sql
-- Safe division (avoid divide by zero)
CASE WHEN denominator = 0 THEN NULL
     ELSE numerator / denominator
END

-- Default values for NULL
COALESCE(column_name, 0)
```

---

## Metric Dependencies

### Metrics Requiring Time Comparison
- YoY Growth → Needs data from same period last year
- MoM Growth → Needs data from previous month
- Trend Analysis → Needs at least 3 time periods

### Metrics Requiring Multiple Tables
- Customer Satisfaction vs Conversion → Join customer_feedback + web_analytics
- Revenue vs Sentiment → Use pc_sales (already contains both)

### Metrics Requiring Calculated Fields
- Conversion Rate → conversion_count / visitor_count
- NPS → Complex calculation with CASE statements
- AOV → total_revenue / order_count

---

## Quick Reference Table

| Metric | Formula | Key Columns | Primary Table |
|--------|---------|-------------|---------------|
| Conversion Rate | (conversions / visitors) × 100 | conversion_count, visitor_count | web_analytics |
| AOV | revenue / orders | sale_amount, order_id | pc_sales |
| NPS | % promoters - % detractors | nps_score | customer_feedback |
| CSAT | (satisfied / total) × 100 | csat_score | customer_feedback |
| Sentiment | AVG(sentiment_score) | sentiment_score | pc_sales |
| YoY Growth | ((current - prior) / prior) × 100 | date, metric | any |
| Churn Rate | (churned / total) × 100 | customer_id, date | pc_sales |
| CLV | SUM(revenue) per customer | sale_amount, customer_id | pc_sales |

---

## Common Pitfalls to Avoid

1. **Don't assume time periods** - Always ask for clarification
2. **Don't assume cities** - Always require explicit city filter
3. **Don't use pre-calculated if recalculation is needed** - Check if time filters match
4. **Don't ignore NULLs** - Always consider NULL handling
5. **Don't mix incompatible scales** - NPS (0-10) vs CSAT (1-5) vs Sentiment (-1 to +1)
