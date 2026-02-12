# Business Glossary

## Overview
This document defines business terms, concepts, and terminology used in our data analysis.

---

## Customer Metrics

### Net Promoter Score (NPS)
- **Category:** Customer Loyalty Metric
- **Scale:** 0 to 10
- **Question:** "How likely are you to recommend our product/service to a friend or colleague?"
- **Classification:**
  - **Promoters (9-10):** Loyal enthusiasts who will keep buying and refer others
  - **Passives (7-8):** Satisfied but unenthusiastic customers who may switch to competitors
  - **Detractors (0-6):** Unhappy customers who can damage your brand through negative word-of-mouth
- **Calculation:** % Promoters - % Detractors
- **Industry Standard:** Yes
- **When to Use:** Measure overall customer loyalty and brand health

### Customer Satisfaction Score (CSAT)
- **Category:** Transaction-Level Satisfaction
- **Scale:** 1 to 5
- **Question:** "How satisfied were you with your experience?"
- **Interpretation:**
  - 5: Very Satisfied
  - 4: Satisfied
  - 3: Neutral
  - 2: Dissatisfied
  - 1: Very Dissatisfied
- **Success Threshold:** Score of 4 or 5
- **When to Use:** Measure satisfaction immediately after a specific interaction or transaction

### Sentiment Score
- **Category:** Emotional Analysis
- **Scale:** -1.0 to +1.0
- **Source:** Analyzed from customer feedback, reviews, and comments
- **Interpretation:**
  - +0.5 to +1.0: Very Positive (delighted customers)
  - +0.2 to +0.5: Positive (satisfied customers)
  - -0.2 to +0.2: Neutral (indifferent customers)
  - -0.5 to -0.2: Negative (dissatisfied customers)
  - -1.0 to -0.5: Very Negative (angry customers)
- **When to Use:** Understand emotional tone of customer interactions

### Customer Lifetime Value (CLV)
- **Category:** Revenue Metric
- **Definition:** Total revenue a customer will generate over their entire relationship with the company
- **Importance:** Helps determine how much to spend on customer acquisition
- **Formula:** Average Order Value × Purchase Frequency × Customer Lifespan
- **When to Use:** Marketing budget allocation, customer segmentation

### Churn Rate
- **Category:** Retention Metric
- **Definition:** Percentage of customers who stop doing business with you
- **Typical Period:** Measured monthly or annually
- **Formula:** (Customers Lost / Total Customers at Start of Period) × 100
- **Industry Benchmark:** Varies by industry (SaaS: 5-7% monthly, E-commerce: 60-80% annually)
- **When to Use:** Identify retention problems and predict future revenue

---

## Conversion Metrics

### Conversion Rate
- **Category:** E-commerce Performance
- **Definition:** Percentage of visitors who complete a desired action (usually a purchase)
- **Formula:** (Conversions / Total Visitors) × 100
- **Industry Average:** 2-3% for e-commerce
- **Good Rate:** Above 3%
- **Excellent Rate:** Above 5%
- **Factors Affecting:** Website UX, pricing, product selection, checkout process
- **When to Use:** Measure effectiveness of website and marketing campaigns

### Bounce Rate
- **Category:** Website Engagement
- **Definition:** Percentage of visitors who leave after viewing only one page
- **Formula:** (Single-Page Sessions / Total Sessions) × 100
- **Good Rate:** Below 40%
- **Concerning Rate:** Above 60%
- **When to Use:** Identify pages with poor engagement

### Average Order Value (AOV)
- **Category:** Revenue Metric
- **Definition:** Average amount spent per order
- **Formula:** Total Revenue / Number of Orders
- **Strategies to Increase:** Cross-selling, upselling, minimum order discounts
- **When to Use:** Revenue optimization, promotional planning

---

## Geographical Terms

### City
- **Definition:** Specific metropolitan area where transaction occurred
- **Examples:** bangalore, delhi, mumbai, chennai, hyderabad, pune, kolkata
- **Format:** Lowercase, single word
- **Usage:** Most granular level of location filtering

### Region / Location
- **Definition:** Broader geographical grouping
- **Categories:**
  - **North:** Delhi, Chandigarh, Lucknow
  - **South:** Bangalore, Chennai, Hyderabad
  - **West:** Mumbai, Pune, Ahmedabad
  - **East:** Kolkata, Bhubaneswar
  - **Central:** Indore, Bhopal, Nagpur
- **Usage:** Regional analysis and comparison

---

## Time-Based Terms

### Quarter (Q1, Q2, Q3, Q4)
- **Q1:** January 1 - March 31
- **Q2:** April 1 - June 30
- **Q3:** July 1 - September 30
- **Q4:** October 1 - December 31

### Fiscal Year vs Calendar Year
- **Calendar Year:** January 1 - December 31
- **Fiscal Year:** Varies by company (often April 1 - March 31 in India)
- **Default:** Unless specified, assume calendar year

### Year-over-Year (YoY)
- **Definition:** Comparison with the same period in the previous year
- **Example:** Q4 2024 vs Q4 2023
- **Purpose:** Identify long-term trends, account for seasonality

### Month-over-Month (MoM)
- **Definition:** Comparison with the previous month
- **Example:** November 2024 vs October 2024
- **Purpose:** Identify short-term trends and immediate changes

### Last Month
- **Definition:** The previous complete calendar month
- **Example:** If today is December 15, 2024, "last month" = November 2024
- **NOT:** Last 30 days (which would be November 15 - December 15)

### This Month
- **Definition:** The current calendar month to date
- **Example:** If today is December 15, 2024, "this month" = December 1-15, 2024

---

## Product & Sales Terms

### Product Category
- **Definition:** High-level classification of products
- **Categories:** Electronics, Furniture, Clothing, Books, Home & Garden
- **Usage:** Category-level performance analysis

### SKU (Stock Keeping Unit)
- **Definition:** Unique identifier for each product variant
- **Example:** If a t-shirt comes in 3 colors and 4 sizes, it has 12 SKUs
- **Usage:** Inventory management, sales tracking

### Revenue
- **Definition:** Total income from sales before deductions
- **Formula:** Price × Quantity
- **Currency:** INR (Indian Rupees)
- **NOT to be confused with:** Profit (which subtracts costs)

### Transaction
- **Definition:** A single purchase event
- **Synonyms:** Order, Sale, Purchase
- **Components:** Customer, Product(s), Amount, Date, Location

---

## Web Analytics Terms

### Visitor
- **Definition:** Unique person who visits the website
- **Counted:** Once per time period regardless of number of visits
- **Synonyms:** Unique visitor, user

### Session
- **Definition:** A single visit to the website
- **Duration:** Typically expires after 30 minutes of inactivity
- **Note:** One visitor can have multiple sessions

### Page View
- **Definition:** A single page load
- **Note:** One session can have multiple page views

### Traffic Source
- **Definition:** How visitors arrived at the website
- **Types:**
  - **Organic:** Search engine results (not paid)
  - **Paid:** Paid advertising (Google Ads, etc.)
  - **Social:** Social media platforms
  - **Email:** Email campaigns
  - **Direct:** Typed URL directly or bookmarks
  - **Referral:** Links from other websites

---

## Data Quality Terms

### NULL
- **Definition:** Missing or unknown value
- **NOT the same as:** Zero or empty string
- **Handling:** Depends on context
  - Sometimes exclude (AVG, COUNT(column))
  - Sometimes include (COUNT(*))
  - Sometimes replace with default (COALESCE)

### Outlier
- **Definition:** Data point significantly different from others
- **Examples:**
  - Sale amount of ₹1,000,000 when typical is ₹500-₹2,000
  - Sentiment score of -1.0 when most are positive
- **Handling:** Investigate before removing (might be legitimate)

### Sample Size
- **Definition:** Number of data points in analysis
- **Importance:** Small sample sizes can be misleading
- **Rule of Thumb:** Need at least 30 data points for meaningful statistics

---

## Statistical Terms

### Average (Mean)
- **Definition:** Sum of values divided by count
- **Formula:** SUM(values) / COUNT(values)
- **Note:** Sensitive to outliers
- **When to Use:** Normal distribution without extreme outliers

### Median
- **Definition:** Middle value when sorted
- **Calculation:** 50th percentile
- **Note:** NOT sensitive to outliers
- **When to Use:** Skewed distributions with outliers

### Trend
- **Definition:** General direction of movement over time
- **Types:**
  - **Upward:** Increasing over time
  - **Downward:** Decreasing over time
  - **Flat:** No significant change
  - **Seasonal:** Repeating patterns based on time of year

### Correlation
- **Definition:** Statistical relationship between two variables
- **Range:** -1.0 to +1.0
- **Interpretation:**
  - +1.0: Perfect positive correlation
  - 0.0: No correlation
  - -1.0: Perfect negative correlation
- **Important:** Correlation ≠ Causation

---

## Business Context Rules

### When User Says "Sentiment"
- **They Mean:** sentiment_score column from pc_sales table
- **Expected Output:** Numerical score between -1.0 and +1.0
- **Additional Context:** May want to know positive/negative/neutral counts

### When User Says "Satisfaction"
- **Could Mean:**
  1. CSAT score (1-5 scale) from customer_feedback
  2. NPS score (0-10 scale) from customer_feedback
  3. Sentiment score (-1 to +1) from pc_sales
- **Action:** Clarify which metric they want, or provide all three

### When User Says "Conversion"
- **They Mean:** Conversion rate metric
- **Required:** visitor_count and conversion_count from web_analytics
- **Output:** Percentage (0-100%)
- **Context:** May want to know about specific time period or traffic source

### When User Says "Sales"
- **Could Mean:**
  1. Revenue (sale_amount from pc_sales)
  2. Number of transactions (COUNT from pc_sales)
  3. Both revenue and transaction count
- **Action:** Provide both unless they specify

### When User Says "Bangalore" (or any city)
- **Action:** ALWAYS filter by exact city
- **NEVER:** Show data for all cities and assume they meant something else
- **Column:** city column (case-insensitive match)

### When User Says "Last Month" or "Q4"
- **Action:** Ask for specific year if not provided
- **NEVER:** Assume current year or "most recent"
- **Example:** "Q4" could mean Q4 2024, Q4 2023, etc.

---

## Data Governance

### Personal Identifiable Information (PII)
- **Definition:** Data that can identify a specific individual
- **Examples:** customer_id, email, phone number, full address
- **Handling:** May have access restrictions

### Data Freshness
- **Definition:** How recent the data is
- **Typical Lag:** 24 hours for batch-processed data, real-time for streaming
- **Impact:** "Today's" data might not be complete

### Data Lineage
- **Definition:** Origin and transformation history of data
- **Importance:** Understanding how metrics are calculated

---

## Common Abbreviations

- **AOV:** Average Order Value
- **CSAT:** Customer Satisfaction Score
- **CLV:** Customer Lifetime Value
- **CR:** Conversion Rate
- **MoM:** Month-over-Month
- **NPS:** Net Promoter Score
- **SKU:** Stock Keeping Unit
- **YoY:** Year-over-Year
- **KPI:** Key Performance Indicator
- **ROI:** Return on Investment

---

## Questions to Always Ask

### For Time-Based Queries
- ❓ Which time period? (specific dates, month, quarter, year)
- ❓ Calendar year or fiscal year?
- ❓ Include current incomplete period?

### For Location-Based Queries
- ❓ Which city/region?
- ❓ Single location or comparison across locations?
- ❓ Include NULL/unknown locations?

### For Metric Calculations
- ❓ Which specific metric? (if ambiguous like "satisfaction")
- ❓ Include all customers or filter by segment?
- ❓ Raw numbers or percentages?

### For Comparisons
- ❓ What to compare against? (time period, location, category)
- ❓ Absolute values or percentage change?
- ❓ Which metric is primary?

---

## Red Flags - Never Do This

❌ **Don't assume default cities** - Always require explicit city filter
❌ **Don't assume "current" or "latest"** - Always ask for specific time period
❌ **Don't mix metrics with different scales** - NPS (0-10) ≠ CSAT (1-5) ≠ Sentiment (-1 to +1)
❌ **Don't ignore NULL values** - Always consider how to handle them
❌ **Don't return irrelevant data** - If user asks for Bangalore, don't show Delhi
❌ **Don't use pre-calculated values when filters don't match** - Recalculate if needed
❌ **Don't extrapolate incomplete data** - If month isn't over, don't project full month

---

## Best Practices

✅ **Always validate filters are applied** - Check result matches question
✅ **Always provide context** - Include time period, location, sample size
✅ **Always explain calculations** - Show formula used for metrics
✅ **Always handle NULLs explicitly** - Document how NULLs are treated
✅ **Always verify data makes sense** - 150% conversion rate = error
✅ **Always cite sources** - Which table and columns used
