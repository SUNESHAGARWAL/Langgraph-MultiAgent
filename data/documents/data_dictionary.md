# Data Dictionary

## Overview
This document provides detailed definitions of all columns in our Unity Catalog tables.

---

## Table: pc_sales (Product Catalog Sales)

### Description
Contains product sales data with customer sentiment analysis and location information.

### Columns

#### sentiment_score
- **Type:** DOUBLE (Decimal number)
- **Range:** -1.0 to +1.0
- **Description:** Customer sentiment score for the transaction
  - Negative values (-1.0 to -0.1): Negative sentiment
  - Zero or near-zero (-0.1 to +0.1): Neutral sentiment
  - Positive values (+0.1 to +1.0): Positive sentiment
- **Source:** Calculated from customer feedback, reviews, and ratings
- **Null Values:** Not allowed (always has a value)
- **Business Context:** Higher scores indicate better customer satisfaction

#### city
- **Type:** STRING (Text)
- **Description:** City where the sale occurred
- **Valid Values:** bangalore, delhi, mumbai, chennai, hyderabad, pune, kolkata
- **Case:** Lowercase
- **Null Values:** Allowed (some records may not have city information)
- **Business Context:** Used for geographical analysis and regional performance

#### location
- **Type:** STRING (Text)
- **Description:** Broader geographical region
- **Valid Values:** North, South, East, West, Central
- **Null Values:** Allowed
- **Business Context:** Used for regional aggregation when city-level is too granular

#### product_name
- **Type:** STRING (Text)
- **Description:** Name of the product sold
- **Null Values:** Not allowed
- **Business Context:** Used for product-level analysis

#### product_category
- **Type:** STRING (Text)
- **Description:** Category of the product
- **Valid Values:** Electronics, Furniture, Clothing, Books, Home & Garden
- **Null Values:** Allowed
- **Business Context:** Used for category-level performance analysis

#### date
- **Type:** TIMESTAMP (Date and time)
- **Format:** YYYY-MM-DD HH:MM:SS
- **Description:** Date and time when the sale occurred
- **Null Values:** Not allowed
- **Business Context:** Used for time-series analysis and trend identification

#### sale_amount
- **Type:** DOUBLE (Decimal number)
- **Description:** Total sale amount in local currency
- **Currency:** INR (Indian Rupees)
- **Null Values:** Not allowed
- **Business Context:** Used for revenue calculations

#### customer_id
- **Type:** STRING (Text)
- **Description:** Unique identifier for the customer
- **Format:** CUST-XXXXXX (6 digits)
- **Null Values:** Allowed (for walk-in customers)
- **Business Context:** Used for customer-level analysis

---

## Table: web_analytics (Website Analytics)

### Description
Contains website traffic and conversion data.

### Columns

#### visitor_count
- **Type:** INTEGER (Whole number)
- **Description:** Number of unique visitors to the website
- **Range:** 0 or positive integers
- **Null Values:** Not allowed
- **Business Context:** Denominator for conversion rate calculation

#### conversion_count
- **Type:** INTEGER (Whole number)
- **Description:** Number of visitors who completed a purchase
- **Range:** 0 or positive integers
- **Must be:** Less than or equal to visitor_count
- **Null Values:** Not allowed
- **Business Context:** Numerator for conversion rate calculation

#### conversion_rate
- **Type:** DOUBLE (Decimal number)
- **Range:** 0.0 to 100.0 (percentage)
- **Description:** Pre-calculated conversion rate
- **Formula:** (conversion_count / visitor_count) × 100
- **Null Values:** Allowed (if not pre-calculated)
- **Business Context:** Key performance indicator for e-commerce effectiveness

#### session_count
- **Type:** INTEGER (Whole number)
- **Description:** Total number of sessions (including repeat visitors)
- **Range:** 0 or positive integers
- **Must be:** Greater than or equal to visitor_count
- **Null Values:** Not allowed
- **Business Context:** Used for engagement analysis

#### date
- **Type:** DATE (Date only, no time)
- **Format:** YYYY-MM-DD
- **Description:** Date of the analytics data
- **Null Values:** Not allowed
- **Business Context:** Used for time-series analysis

#### source
- **Type:** STRING (Text)
- **Description:** Traffic source
- **Valid Values:** organic, paid, social, email, direct, referral
- **Null Values:** Allowed
- **Business Context:** Used for marketing channel analysis

---

## Table: customer_feedback (Customer Feedback & Satisfaction)

### Description
Contains customer satisfaction surveys and NPS scores.

### Columns

#### nps_score
- **Type:** INTEGER (Whole number)
- **Range:** 0 to 10
- **Description:** Net Promoter Score from customer survey
  - 0-6: Detractors
  - 7-8: Passives
  - 9-10: Promoters
- **Null Values:** Not allowed
- **Business Context:** Industry-standard customer loyalty metric

#### csat_score
- **Type:** INTEGER (Whole number)
- **Range:** 1 to 5
- **Description:** Customer Satisfaction (CSAT) score
  - 1: Very Dissatisfied
  - 2: Dissatisfied
  - 3: Neutral
  - 4: Satisfied
  - 5: Very Satisfied
- **Null Values:** Allowed (not all customers provide CSAT)
- **Business Context:** Immediate satisfaction metric

#### customer_id
- **Type:** STRING (Text)
- **Description:** Unique identifier for the customer
- **Format:** CUST-XXXXXX (6 digits)
- **Null Values:** Not allowed
- **Business Context:** Links to customer records

#### city
- **Type:** STRING (Text)
- **Description:** City of the customer
- **Valid Values:** bangalore, delhi, mumbai, chennai, hyderabad, pune, kolkata
- **Null Values:** Allowed
- **Business Context:** Used for regional satisfaction analysis

#### feedback_date
- **Type:** TIMESTAMP (Date and time)
- **Description:** When the feedback was submitted
- **Null Values:** Not allowed
- **Business Context:** Used for trend analysis

#### feedback_text
- **Type:** STRING (Text)
- **Description:** Optional text feedback from customer
- **Null Values:** Allowed (not mandatory)
- **Business Context:** Used for qualitative analysis

---

## Common Filtering Columns

### Date/Time Columns
- Always use proper date ranges (BETWEEN, >=, <=)
- Never assume "current" without explicit user instruction
- Common formats: YYYY-MM-DD, Q1/Q2/Q3/Q4 YYYY, "last month", "this year"

### Location Columns
- **city:** Exact city name (case-insensitive)
- **location/region:** Broader regional grouping
- Never assume a default city - always use exact filter

### Customer Identification
- **customer_id:** Primary identifier
- Always join on exact match
- Null customer_ids represent anonymous/walk-in customers

---

## Important Notes

1. **NULL Values:**
   - When a column allows nulls, always consider NULL handling in queries
   - Use COALESCE or IS NULL checks appropriately

2. **Data Types:**
   - INTEGER: Whole numbers only (no decimals)
   - DOUBLE: Decimal numbers (floating point)
   - STRING: Text (case-sensitive unless specified)
   - TIMESTAMP: Full date and time
   - DATE: Date only (no time component)

3. **Case Sensitivity:**
   - City names are lowercase
   - Customer IDs are uppercase
   - Product names use mixed case

4. **Valid Ranges:**
   - Always validate that values fall within expected ranges
   - sentiment_score: -1.0 to +1.0
   - nps_score: 0 to 10
   - csat_score: 1 to 5
   - conversion_rate: 0.0 to 100.0

---

## Quick Reference

### Sentiment Analysis
```
Column: sentiment_score
Table: pc_sales
Range: -1.0 (very negative) to +1.0 (very positive)
```

### Location Filtering
```
Column: city
Tables: pc_sales, customer_feedback
Values: bangalore, delhi, mumbai, chennai, hyderabad, pune, kolkata
```

### Conversion Metrics
```
Table: web_analytics
Formula: (conversion_count / visitor_count) × 100
Columns: conversion_count, visitor_count, conversion_rate
```

### Customer Satisfaction
```
NPS: 0-10 scale (customer_feedback.nps_score)
CSAT: 1-5 scale (customer_feedback.csat_score)
Sentiment: -1 to +1 scale (pc_sales.sentiment_score)
```
