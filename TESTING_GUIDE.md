# Testing Guide - v5.0 Bug Fixes

**Date:** 2026-02-11
**Branch:** `claude/setup-docs-and-tests-vtX1W`
**Commits:**
- `fbf7523` - Fix infinite schema analysis loop and LLM hallucinations
- `db4d684` - Trust user specifications instead of asking redundant confirmations

---

## 🐛 Issues Fixed

### Issue 1: Infinite Schema Analysis Loop ✅
**Problem:** System kept routing to schema analysis repeatedly (iterations 0-5 all went to schema)

**Root Cause:** Clarification messages didn't contain proper markers for supervisor to detect

**Fix Applied:**
- Added `[Schema Analysis Complete - Needs Clarification]` marker
- Updated supervisor to detect both "Schema Analysis" and "[Schema Analysis Complete"
- Proper routing to "human" when clarification needed

### Issue 2: LLM Hallucinating Data Availability ✅
**Problem:** LLM said "data only available up to October 2023" when user had October 2025 data

**Root Cause:** LLM trained on data up to Oct 2023, wrongly assumed user's data same

**Fix Applied:**
- Added explicit instruction: "DO NOT make assumptions about data availability"
- Schema shows STRUCTURE not CONTENTS
- Trust user when they specify dates

### Issue 3: Redundant Clarification Questions ✅
**Problem:** System kept asking "Can you confirm if data for October 2025 is available?" even after user provided "pc_sales, oct 2025, bangalore" multiple times

**Root Cause:** LLM didn't understand that providing specifications = confirmation

**Fix Applied:**
- Changed prompt from defensive to trusting
- If user provides TABLE + DATE + LOCATION → Mark as ANSWERABLE: YES
- Only ask clarification if information is MISSING (not yet provided)

---

## 🧪 Test Cases

### Test Case 1: Simple Query with All Details
**Test the fix for redundant questions**

```bash
python -m src.main_simple
```

**Test Flow:**
```
Step 1: Ask vague question
🤔 You: show me sentiment

Expected: System asks for clarification
✓ "I need some clarification: Which table? Date range? Location?"

Step 2: Provide all details
🤔 You: pc_sales, oct 2025, bangalore

Expected: System proceeds WITHOUT asking "can you confirm"
✓ Should go to query planning → Genie execution → Answer
✗ Should NOT ask "Can you confirm if data for October 2025 is available?"

Step 3: Check iterations
Expected: 2-3 iterations total (schema → human → query → genie → synthesis)
✗ Should NOT loop back to schema
```

### Test Case 2: Direct Query (No Clarification Needed)
**Test that system still works when all info provided upfront**

```
🤔 You: What is sentiment for bangalore from pc_sales in october 2025?

Expected:
✓ Goes straight to query planning (no clarification)
✓ Executes query
✓ Returns answer
✓ 2-3 iterations total
```

### Test Case 3: Multi-Turn with Memory
**Test conversation memory still works**

```
Step 1:
🤔 You: what is sentiment for bangalore from pc_sales?

Expected: Asks for date range
✓ "What date range should I analyze?"

Step 2:
🤔 You: october 2025

Expected: Proceeds with query
✓ Uses bangalore (from step 1) + october 2025 (from step 2)
✓ Does NOT ask to confirm data availability
```

### Test Case 4: Truly Unanswerable Query
**Test that legitimate clarification requests still work**

```
🤔 You: show me data

Expected: Asks for specifics
✓ "What kind of data? Which table? What information are you looking for?"
```

---

## 📊 Expected Behavior

### Before Fixes (v4.0 and early v5.0)
```
User: show me sentiment
→ Schema analysis (iteration 0)
→ Schema analysis (iteration 1) ← LOOP!
→ Schema analysis (iteration 2) ← LOOP!
→ Schema analysis (iteration 3) ← LOOP!
→ Schema analysis (iteration 4) ← LOOP!
→ Forced synthesis (iteration 5)
→ Incomplete/wrong answer

User: pc_sales, oct 2025, bangalore
→ Schema: "Can you confirm if data for October 2025 is available?" ← REDUNDANT!
User: pc_sales, oct 2025, bangalore (again)
→ Schema: "Can you confirm if data for October 2025 is available?" ← STILL ASKING!
```

### After Fixes (Current v5.0)
```
User: show me sentiment
→ Schema analysis (iteration 0)
→ Human clarification: "Which table? Date range? Location?" (iteration 1)

User: pc_sales, oct 2025, bangalore
→ Query planning (iteration 2) ← PROCEEDS!
→ Genie execution (iteration 3)
→ Synthesis (iteration 4)
→ Final answer ✓
```

---

## 🔍 How to Verify Fixes

### Check 1: No Infinite Loops
Watch the iteration counter in logs:
```
⚙️  Iteration 0: supervisor → schema
⚙️  Iteration 1: supervisor → human
⚙️  Iteration 2: supervisor → query
⚙️  Iteration 3: supervisor → genie
⚙️  Iteration 4: supervisor → synthesis
```

✓ Should progress through different agents
✗ Should NOT stay on schema for multiple iterations

### Check 2: No Data Availability Questions
When user provides details, watch for:

✓ System should say: "Formatting query for Genie..."
✗ System should NOT ask: "Can you confirm if data for X is available?"

### Check 3: Clarification Markers
In logs, look for:
```
[Schema Analysis Complete - Needs Clarification]
```

✓ This marker should appear when clarification needed
✓ Supervisor should detect it and route to "human"

### Check 4: State Transitions
Check the `next_agent` in logs:

**Good Flow:**
```
schema → human → query → genie → synthesis → __end__
```

**Bad Flow (old bug):**
```
schema → schema → schema → schema → synthesis
```

---

## 🚨 Common Issues During Testing

### Issue: "ModuleNotFoundError"
**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: Still seeing old behavior
**Solution:** Make sure you're running the correct file:
```bash
# ✓ Correct
python -m src.main_simple

# ✗ Wrong (old v4 system)
python src/main_clean.py
python -m src.main_clean
```

### Issue: Configuration errors
**Solution:** Check .env file:
```bash
grep -E "(AZURE_OPENAI|DATABRICKS|GENIE)" .env
```

---

## 📈 Success Criteria

### All tests pass if:
1. ✅ No infinite schema analysis loops
2. ✅ System stops asking "can you confirm data available" after user provides details
3. ✅ Clarification flow works (asks when info missing, proceeds when provided)
4. ✅ Iteration count is reasonable (2-5 iterations, not 10+)
5. ✅ Conversation memory works across turns
6. ✅ Final answers are comprehensive and accurate

---

## 🎯 What Was Changed in Code

### File: `src/agent_simple.py`

**Change 1: Schema Analysis Prompt (lines 177-186)**
```python
# OLD (defensive approach)
"""
Analyze the schemas and determine if the question is answerable.
CRITICAL: DO NOT make assumptions about data availability!
"""

# NEW (trusting approach)
"""
CRITICAL RULES:
1. If user provides TABLE NAME + DATE + LOCATION → Mark as ANSWERABLE: YES
2. DO NOT ask "can you confirm if data for X is available" - TRUST the user!
3. Schema shows STRUCTURE not CONTENTS - you cannot know what data exists
4. If user specifies details → ASSUME data exists and proceed
5. Only ask clarification if MISSING information (not provided yet)
"""
```

**Change 2: Clarification Message Format (lines 259-273)**
```python
# Added explicit marker for supervisor
clarification_msg = f"""[Schema Analysis Complete - Needs Clarification]

I found data that matches your question, but I need some clarification:

{clarification}
"""
```

**Change 3: Supervisor Detection (lines 636-645)**
```python
# Check for both markers
has_schema_analysis = any(
    "Schema Analysis" in str(msg.content) or
    "[Schema Analysis Complete" in str(msg.content)
    for msg in messages if isinstance(msg, AIMessage)
)

# Detect clarification state
needs_clarification = any(
    "Needs Clarification" in str(msg.content) or
    "need some clarification" in str(msg.content)
    for msg in messages if isinstance(msg, AIMessage)
)
```

---

## 📝 Test Results Template

Use this template to document your test results:

```
Test Date: ___________
Tester: ___________

Test Case 1: Simple Query with All Details
- Vague question asked: [ ] Pass [ ] Fail
- Clarification received: [ ] Pass [ ] Fail
- Details provided: [ ] Pass [ ] Fail
- System proceeded without redundant questions: [ ] Pass [ ] Fail
- Answer received: [ ] Pass [ ] Fail
- Iterations count: _____
- Notes: ___________

Test Case 2: Direct Query
- Query executed immediately: [ ] Pass [ ] Fail
- No clarification needed: [ ] Pass [ ] Fail
- Answer received: [ ] Pass [ ] Fail
- Iterations count: _____
- Notes: ___________

Test Case 3: Multi-Turn with Memory
- First question clarification: [ ] Pass [ ] Fail
- Second response uses context: [ ] Pass [ ] Fail
- Answer received: [ ] Pass [ ] Fail
- Notes: ___________

Test Case 4: Unanswerable Query
- Clarification requested: [ ] Pass [ ] Fail
- Questions were reasonable: [ ] Pass [ ] Fail
- Notes: ___________

Overall Result: [ ] All Pass [ ] Some Failed

Issues Found:
1. ___________
2. ___________
```

---

## 🔧 Debugging Tips

### Enable Detailed Logging
Check logs for these key messages:

**Schema Analysis:**
```
→ Routing to: schema (no analysis yet)
Schema analysis result: ANSWERABLE: YES/NO
```

**Clarification:**
```
[Schema Analysis Complete - Needs Clarification]
→ Routing to: human (needs clarification)
```

**Query Execution:**
```
→ Routing to: query (schema done, answerable)
Genie Query: [exact query sent]
```

### Check State Variables
In logs, verify:
- `iterations`: Should increment 0, 1, 2, 3...
- `is_answerable`: Should be False during clarification, True after
- `next_agent`: Should progress through different agents
- `schema_info`: Should contain actual table/column information

---

## 📞 If Tests Fail

### Infinite Loop Still Happening
1. Check which agent it's looping on (look at "Routing to:")
2. Verify clarification message contains `[Schema Analysis Complete` marker
3. Check supervisor logic is detecting the marker

### Still Asking "Can you confirm data available"
1. Verify you're running latest code: `git log --oneline -1` should show `db4d684`
2. Check schema analysis prompt contains new CRITICAL RULES
3. Try restarting the system (may have cached old prompts)

### System Not Asking for Clarification When It Should
1. Check if query is truly vague (missing table, date, or location)
2. Verify schema analysis is running (check logs)
3. Ensure clarification logic is enabled

---

**Version:** 5.0.0-simple
**Status:** ✅ All critical bugs fixed
**Ready for Testing:** Yes
**Last Updated:** 2026-02-11
