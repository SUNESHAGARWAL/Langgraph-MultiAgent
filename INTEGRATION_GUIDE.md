# Integration Guide: Enhanced RAG Multi-Agent System

## Overview
This guide explains how to integrate the enhanced agent components into your system.

**What's New:**
1. ✅ **Strict Schema Analyzer** - No assumptions about cities/time ranges
2. ✅ **Query Decomposition** - Breaks complex questions into sub-questions
3. ✅ **Result Validation** - Catches incorrect Genie responses
4. ✅ **Follow-up Generation** - Creates analytical follow-up questions
5. ✅ **RAG Documents** - Business knowledge base for better understanding
6. ✅ **Debug Notebook** - Section-wise testing and debugging

---

## File Structure

```
Langgraph-MultiAgent/
├── src/
│   ├── agent_simple.py          # Original agent (keep as backup)
│   ├── agent_enhanced.py        # NEW: Enhanced components
│   └── ...
├── notebooks/
│   └── debug_rag_system.ipynb   # NEW: Debugging notebook
├── data/
│   └── documents/               # NEW: RAG documents
│       ├── README.md
│       ├── data_dictionary.md
│       ├── metric_calculations.md
│       └── business_glossary.md
└── INTEGRATION_GUIDE.md         # This file
```

---

## Quick Start

### Step 1: Enable RAG
Edit your `.env` file:
```bash
# Enable RAG
RAG_ENABLED=true
RAG_DOCUMENTS_PATH=./data/documents
RAG_VECTOR_STORE_PATH=./data/vector_stores/rag_index

# RAG Settings
RAG_TOP_K=3
RAG_MIN_SIMILARITY=0.7
RAG_ENABLE_STANDALONE_QA=true
RAG_STANDALONE_THRESHOLD=0.85
```

### Step 2: Test with Debug Notebook
```bash
# Navigate to notebooks directory
cd notebooks

# Launch Jupyter
jupyter notebook debug_rag_system.ipynb

# Run sections 1-3 to verify:
# - Schema reading works
# - Column selection is correct
# - RAG integration is working
```

### Step 3: Integrate Enhanced Components (Optional)
See detailed integration steps below.

---

## Integration Options

### Option 1: Use Debug Notebook Only (Recommended for Testing)
**Best for:** Testing and debugging before making changes

**What you get:**
- Section-wise visibility into each component
- Ability to test column selection logic
- RAG integration testing
- Query planning validation

**How to use:**
1. Run `jupyter notebook notebooks/debug_rag_system.ipynb`
2. Execute each section sequentially
3. Observe outputs and make adjustments
4. Document findings in the notebook

**Pros:**
- No code changes needed
- Safe testing environment
- Easy to iterate and experiment

**Cons:**
- Manual execution (not automated)
- Not integrated into main CLI

---

### Option 2: Integrate Enhanced Components (Full Integration)
**Best for:** Production deployment with improved logic

**What you get:**
- Strict assumption checking
- Query decomposition for complex questions
- Result validation
- Analytical follow-ups
- RAG-enhanced responses

**How to integrate:** See "Full Integration Steps" below.

---

## Full Integration Steps

### Step 1: Import Enhanced Components

Edit `src/agent_simple.py`:

```python
# Add this import at the top
from src.agent_enhanced import (
    create_strict_schema_analyzer,
    create_query_decomposer,
    create_result_validator,
    create_followup_generator
)
```

### Step 2: Replace Schema Analyzer

Find the `create_schema_analysis_agent` usage in `src/agent_simple.py` (around line 1183):

```python
# OLD:
schema_analysis_node = create_schema_analysis_agent(schema_reader, llm)

# NEW (Strict version):
schema_analysis_node = create_strict_schema_analyzer(schema_reader, llm)
```

This change alone will:
- ✅ Prevent automatic city assumptions
- ✅ Prevent automatic time range assumptions
- ✅ Require explicit filters

### Step 3: Add Query Decomposition (Optional)

Add query decomposition before schema analysis:

```python
# In get_agent() function, after RAG node:

# Add decomposition node
decomposer = create_query_decomposer(llm)

# Update graph
graph_builder.add_node("decompose", decomposer)

# Update routing
def supervisor_router(state):
    next_agent = state.get("next_agent", "")

    # After RAG, go to decomposition
    if state.get("rag_checked") and not state.get("query_decomposed"):
        return "decompose"

    # After decomposition, go to schema analysis
    if state.get("query_decomposed") and not state.get("schema_analyzed"):
        return "schema"

    # ... rest of routing logic
```

### Step 4: Add Result Validation (Optional)

Add validation after Genie execution:

```python
# In get_agent() function, after genie node:

# Add validation node
validator = create_result_validator(llm)

# Update graph
graph_builder.add_node("validate", validator)

# Update routing
def supervisor_router(state):
    # ... previous routing ...

    # After Genie, go to validation
    if state.get("genie_executed") and not state.get("result_validated"):
        return "validate"

    # After validation, check if passed
    if state.get("result_validated"):
        if state.get("validation_passed"):
            return "synthesis"  # Proceed to final answer
        else:
            # Validation failed - need to fix query
            return "human"  # Ask user or retry
```

### Step 5: Add Follow-up Generation (Optional)

Add follow-up generation after synthesis:

```python
# In get_agent() function, after synthesis node:

# Add follow-up node
followup_gen = create_followup_generator(llm)

# Update graph
graph_builder.add_node("followup", followup_gen)

# Update routing
def supervisor_router(state):
    # ... previous routing ...

    # After synthesis, generate follow-ups
    if state.get("next_agent") == "FINISH" and not state.get("followups_generated"):
        # Generate follow-ups before finishing
        result = followup_gen(state)
        state.update(result)

    return "FINISH"
```

### Step 6: Update AgentState

Add new fields to `AgentState` TypedDict in `src/agent_simple.py`:

```python
class AgentState(TypedDict):
    # ... existing fields ...

    # Query decomposition
    query_decomposed: bool
    sub_questions: list[str]
    decomposition_analysis: str

    # Result validation
    result_validated: bool
    validation_passed: bool
    validation_analysis: str

    # Follow-ups
    followups_generated: bool
    followup_questions: list[str]
    followup_analysis: str
```

### Step 7: Initialize New Fields

Update `main_simple.py` to initialize new fields:

```python
input_state = {
    # ... existing fields ...

    # New fields
    "query_decomposed": False,
    "sub_questions": [],
    "decomposition_analysis": "",

    "result_validated": False,
    "validation_passed": False,
    "validation_analysis": "",

    "followups_generated": False,
    "followup_questions": [],
    "followup_analysis": "",
}
```

---

## Testing Integration

### Test 1: Strict Assumptions
```python
# Before: System might assume "all cities"
User: "Show me sentiment"

# After: System asks for clarification
System: "For which city would you like to see sentiment scores?
         Available: bangalore, delhi, mumbai, chennai, hyderabad"
```

### Test 2: Time Range Assumptions
```python
# Before: System might assume current year
User: "Show sales for Q4"

# After: System asks for year
System: "Q4 of which year? 2023 or 2024?"
```

### Test 3: Query Decomposition
```python
# Before: Single complex query to Genie
User: "Compare sentiment between bangalore and delhi"

# After: Decomposed into 2 queries
System:
  Sub-Question 1: "Show sentiment for bangalore"
  Sub-Question 2: "Show sentiment for delhi"
  Then: Compares results
```

### Test 4: Result Validation
```python
# Before: Wrong city returned, no validation
User: "Show sentiment for bangalore"
Genie: Returns delhi data (incorrect)

# After: Validation catches error
System: "Validation FAILED: Result contains delhi data but user asked for bangalore"
```

### Test 5: Follow-up Generation
```python
# Before: Just returns answer
User: "Show sentiment for bangalore"
System: "Average sentiment: 0.82"

# After: Suggests follow-ups
System: "Average sentiment: 0.82

         Follow-up questions:
         1. Compare bangalore sentiment with other cities
         2. Show sentiment trend over last 3 months
         3. Which products have lowest sentiment in bangalore?"
```

---

## Gradual Integration Strategy

### Phase 1: Testing Only (Week 1)
- ✅ Use debug notebook
- ✅ Enable RAG documents
- ✅ Test with sample questions
- ✅ Document findings

### Phase 2: Strict Analyzer (Week 2)
- ✅ Replace schema analyzer only
- ✅ Test assumption handling
- ✅ Verify no regressions
- ✅ Train users on new behavior

### Phase 3: Validation (Week 3)
- ✅ Add result validation
- ✅ Monitor validation failures
- ✅ Improve error handling
- ✅ Document common issues

### Phase 4: Full Features (Week 4)
- ✅ Add query decomposition
- ✅ Add follow-up generation
- ✅ Full system testing
- ✅ Performance tuning

---

## Configuration Options

### Strict Mode Levels

**Level 1: Relaxed (Original Behavior)**
```python
# Use original agent_simple.py
schema_analysis_node = create_schema_analysis_agent(schema_reader, llm)
```
- Allows some assumptions
- Faster responses
- Less clarification needed

**Level 2: Balanced (Recommended)**
```python
# Use strict analyzer but allow "just proceed"
schema_analysis_node = create_strict_schema_analyzer(schema_reader, llm)
```
- No automatic assumptions
- Users can override with "just proceed"
- Better accuracy

**Level 3: Ultra-Strict (Maximum Validation)**
```python
# Use strict analyzer + validation + decomposition
schema_analysis_node = create_strict_schema_analyzer(schema_reader, llm)
validator = create_result_validator(llm)
decomposer = create_query_decomposer(llm)
```
- No assumptions ever
- Always validates results
- Decomposes complex questions
- Most accurate, slowest

### Environment Variables

Add to `.env`:
```bash
# Enhanced Agent Settings
USE_STRICT_SCHEMA_ANALYSIS=true
USE_QUERY_DECOMPOSITION=true
USE_RESULT_VALIDATION=true
USE_FOLLOWUP_GENERATION=true

# Validation Thresholds
VALIDATION_RETRY_LIMIT=2
DECOMPOSITION_COMPLEXITY_THRESHOLD=3
```

---

## Troubleshooting

### Issue 1: Too Many Clarifications
**Symptom:** System asks for clarification on every query.

**Solutions:**
1. Check if questions are genuinely ambiguous
2. Add more detailed RAG documents
3. Use balanced mode instead of ultra-strict
4. Train users to provide explicit filters

### Issue 2: Query Decomposition Too Aggressive
**Symptom:** Simple questions are unnecessarily broken down.

**Solutions:**
1. Adjust `DECOMPOSITION_COMPLEXITY_THRESHOLD`
2. Review decomposition prompt
3. Add examples of non-decomposable questions

### Issue 3: Validation Failing Incorrectly
**Symptom:** Valid results marked as invalid.

**Solutions:**
1. Review validation prompt
2. Add more context to validation
3. Check for edge cases in validation logic
4. Improve Genie query specificity

### Issue 4: RAG Not Finding Documents
**Symptom:** RAG context always empty.

**Solutions:**
1. Check `RAG_ENABLED=true` in `.env`
2. Verify documents exist in `data/documents/`
3. Lower `RAG_MIN_SIMILARITY` threshold
4. Rebuild index: `rm -rf data/vector_stores/rag_index`
5. Check logs for embedding service errors

### Issue 5: Slow Performance
**Symptom:** Queries take too long.

**Solutions:**
1. Disable optional features (decomposition, follow-ups)
2. Reduce `RAG_TOP_K` (fewer documents)
3. Use caching (`CACHE_ENABLED=true`)
4. Consider using faster model (gpt-4o-mini)

---

## Performance Considerations

### Latency Impact

| Feature | Added Latency | Worth It? |
|---------|---------------|-----------|
| Strict Schema Analysis | +0-200ms | ✅ Yes (prevents errors) |
| Query Decomposition | +500-1000ms | ⚠️ For complex queries only |
| Result Validation | +300-500ms | ✅ Yes (catches errors) |
| Follow-up Generation | +400-600ms | ⚠️ Optional nice-to-have |
| RAG Integration | +200-400ms | ✅ Yes (improves accuracy) |

**Total Additional Latency (all features):** ~2-3 seconds
**Recommended:** Enable strict + validation + RAG only = ~1 second added

### Cost Impact

| Feature | API Calls | Token Usage | Monthly Cost* |
|---------|-----------|-------------|---------------|
| Strict Schema Analysis | Same as before | Similar | ~$0 |
| Query Decomposition | +1 call | +500 tokens | ~+$5 |
| Result Validation | +1 call | +300 tokens | ~+$3 |
| Follow-up Generation | +1 call | +400 tokens | ~+$4 |
| RAG Embeddings | 1 call (cached) | +100 tokens | ~+$1 |

*Estimated for 1000 queries/month with GPT-4

**Recommendation:** Start with strict + validation + RAG = ~+$4/month

---

## Best Practices

### DO:
1. ✅ Start with debug notebook
2. ✅ Enable RAG documents first
3. ✅ Test with real user questions
4. ✅ Integrate one feature at a time
5. ✅ Monitor validation failures
6. ✅ Document edge cases
7. ✅ Train users on new behavior

### DON'T:
1. ❌ Enable all features at once
2. ❌ Skip testing phase
3. ❌ Ignore validation failures
4. ❌ Forget to update AgentState
5. ❌ Deploy without RAG documents
6. ❌ Use ultra-strict mode without user training

---

## Getting Help

### Debug Checklist
- [ ] RAG enabled in `.env`?
- [ ] RAG documents exist in `data/documents/`?
- [ ] Vector store rebuilt after adding documents?
- [ ] Imports added correctly?
- [ ] AgentState fields added?
- [ ] Input state initialized with new fields?
- [ ] Graph routing updated?
- [ ] Logs showing expected behavior?

### Common Error Messages

**Error:** `ModuleNotFoundError: No module named 'agent_enhanced'`
- **Fix:** Check import path, ensure `agent_enhanced.py` is in `src/` directory

**Error:** `KeyError: 'query_decomposed'`
- **Fix:** Add missing fields to `AgentState` and initialize in `input_state`

**Error:** `RAG search failed: No module named 'faiss'`
- **Fix:** Install FAISS: `pip install faiss-cpu` or `pip install faiss-gpu`

**Error:** `Vector store not found`
- **Fix:** Delete and rebuild: `rm -rf data/vector_stores/rag_index`

---

## Next Steps

1. **Week 1:** Use debug notebook, test current system
2. **Week 2:** Enable RAG, add documents
3. **Week 3:** Integrate strict schema analyzer
4. **Week 4:** Add validation
5. **Week 5:** Add decomposition and follow-ups (optional)
6. **Week 6:** Full testing and optimization

---

## Support

- **Documentation:** See `notebooks/debug_rag_system.ipynb` for detailed testing
- **RAG Setup:** See `data/documents/README.md` for adding documents
- **Code Reference:** See `src/agent_enhanced.py` for implementation details

---

**Version:** 2.0.0
**Last Updated:** 2024-12-15
**Maintained By:** Development Team
