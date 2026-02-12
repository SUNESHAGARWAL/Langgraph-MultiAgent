"""
Enhanced Agent Components with Improved Logic
==============================================

This module contains enhanced versions of agent components with:
1. Stricter assumptions handling (no automatic city/time defaults)
2. Query decomposition for complex questions
3. Result validation to catch incorrect Genie responses
4. Follow-up question generation for analytical insights
5. Better error handling

Author: Claude Code
Version: 2.0.0-enhanced
Date: 2024-12-15
"""

import operator
from typing import Any, Dict, Annotated
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# QUERY DECOMPOSITION AGENT
# ============================================================================

def create_query_decomposer(llm):
    """
    Agent that decomposes complex questions into simpler sub-questions.

    This helps ensure:
    - Each sub-question is independently answerable
    - Genie receives clear, focused queries
    - Complex analytical questions are broken down systematically
    """

    def decompose_query(state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("=== Query Decomposition Agent ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Get user question
        user_question = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_question = msg.content
                break

        if not user_question:
            logger.warning("No user question found for decomposition")
            return {
                **state,
                "query_decomposed": False,
                "sub_questions": [],
                "iterations": iterations + 1
            }

        # Decomposition prompt
        decomposition_prompt = f"""You are a query decomposition specialist.

Your task: Analyze if this question needs to be broken down into multiple sub-questions.

═══════════════════════════════════════════════════════════════════════════════
🎯 DECOMPOSITION RULES
═══════════════════════════════════════════════════════════════════════════════

**When to decompose:**
1. Question asks for multiple unrelated metrics
   Example: "Show sentiment AND conversion rate" → 2 separate queries

2. Question requires comparison across dimensions
   Example: "Compare bangalore vs delhi sales" → 2 separate queries

3. Question requires calculation dependent on previous results
   Example: "Show top 3 cities by revenue, then sentiment for each" → 2 sequential queries

4. Question asks for correlation or relationship between metrics
   Example: "Is there a correlation between sentiment and sales?" → 2 queries + analysis

5. Question involves temporal comparison
   Example: "Compare Q4 2024 vs Q4 2023" → 2 queries (one per period)

**When NOT to decompose:**
1. Single, simple question
   Example: "Show sentiment for bangalore" → 1 query

2. Single metric with one filter
   Example: "Conversion rate last month" → 1 query

3. Already atomic question
   Example: "Average NPS score" → 1 query

═══════════════════════════════════════════════════════════════════════════════
📋 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

**DECOMPOSITION NEEDED: YES** or **DECOMPOSITION NEEDED: NO**

If YES:
**Sub-Question 1:** [Clear, atomic question]
**Purpose:** [Why this sub-question is needed]
**Dependencies:** [None, or "Depends on Sub-Question X"]

**Sub-Question 2:** [Clear, atomic question]
**Purpose:** [Why this sub-question is needed]
**Dependencies:** [None, or "Depends on Sub-Question X"]

...

**Synthesis Strategy:** [How to combine results from sub-questions]

If NO:
**Reason:** [Why decomposition is not needed]
**Single Query:** [The question as-is]

═══════════════════════════════════════════════════════════════════════════════
❓ USER QUESTION
═══════════════════════════════════════════════════════════════════════════════
{user_question}

═══════════════════════════════════════════════════════════════════════════════

Analyze this question and determine if decomposition is needed:"""

        try:
            response = llm.invoke([SystemMessage(content=decomposition_prompt)])
            decomp_content = response.content
            logger.info(f"Decomposition Analysis:\n{decomp_content}")

            # Parse result
            if "DECOMPOSITION NEEDED: YES" in decomp_content.upper():
                logger.info("✓ Query will be decomposed into sub-questions")

                # Extract sub-questions
                sub_questions = []
                lines = decomp_content.split("\n")
                for line in lines:
                    if line.startswith("**Sub-Question"):
                        # Extract question text
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            question_text = parts[1].strip().rstrip("*").strip()
                            sub_questions.append(question_text)

                return {
                    **state,
                    "messages": [AIMessage(content=f"Query Decomposition:\n{decomp_content}")],
                    "query_decomposed": True,
                    "sub_questions": sub_questions,
                    "decomposition_analysis": decomp_content,
                    "iterations": iterations + 1
                }
            else:
                logger.info("✓ Query does not need decomposition")
                return {
                    **state,
                    "messages": [AIMessage(content=f"Query Decomposition:\n{decomp_content}")],
                    "query_decomposed": False,
                    "sub_questions": [user_question],  # Single question
                    "decomposition_analysis": decomp_content,
                    "iterations": iterations + 1
                }

        except Exception as e:
            logger.error(f"Query decomposition failed: {e}", exc_info=True)
            # Fallback: treat as single question
            return {
                **state,
                "query_decomposed": False,
                "sub_questions": [user_question],
                "iterations": iterations + 1
            }

    return decompose_query


# ============================================================================
# RESULT VALIDATION AGENT
# ============================================================================

def create_result_validator(llm):
    """
    Agent that validates Genie's response matches the user's question.

    This catches issues like:
    - Wrong city returned (asked bangalore, got delhi)
    - Missing filters (asked for time range, got all time)
    - Incorrect calculations
    - Empty or error results
    """

    def validate_result(state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("=== Result Validation Agent ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Get original question
        original_question = state.get("original_question", "")
        if not original_question:
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    original_question = msg.content
                    break

        # Get Genie result
        genie_result = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and ("Genie Results:" in msg.content or "Query" in msg.content):
                genie_result = msg.content
                break

        if not original_question or not genie_result:
            logger.warning("Cannot validate - missing question or result")
            return {
                **state,
                "result_validated": False,
                "validation_passed": False,
                "iterations": iterations + 1
            }

        # Validation prompt
        validation_prompt = f"""You are a result validation specialist.

Your task: Verify that Genie's response correctly answers the user's question.

═══════════════════════════════════════════════════════════════════════════════
🔍 VALIDATION CHECKS
═══════════════════════════════════════════════════════════════════════════════

1. **Filter Validation:**
   - If user asked for "bangalore", does result ONLY contain bangalore?
   - If user asked for "Q4 2024", does result ONLY contain Q4 2024 data?
   - If user asked for specific filter, is it applied?

2. **Relevance Check:**
   - Does the result relate to the question?
   - If user asked for "sentiment", does result show sentiment data?
   - If user asked for "conversion rate", does result show conversion data?

3. **Completeness Check:**
   - Does it answer ALL aspects of the question?
   - If user asked for multiple things, are all included?

4. **Error Detection:**
   - Are there error messages in the result?
   - Is the result empty when it shouldn't be?
   - Are there obvious data issues (negative percentages, impossible values)?

5. **Assumption Detection:**
   - Did the system assume something NOT in the question?
   - Example: User asked "sentiment", got result for "delhi" (didn't ask for city)
   - Example: User asked "bangalore", got result for multiple cities

═══════════════════════════════════════════════════════════════════════════════
📋 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

**VALIDATION: PASSED** or **VALIDATION: FAILED**

**Reasoning:**
[Explain validation decision clearly]

**Issues Found (if any):**
- [Issue 1]: [Description]
- [Issue 2]: [Description]

**Suggested Fix (if failed):**
[What should be done to fix the issue]

**Follow-up Questions (if needed):**
- [Question to clarify or get missing information]

═══════════════════════════════════════════════════════════════════════════════
❓ ORIGINAL QUESTION
═══════════════════════════════════════════════════════════════════════════════
{original_question}

═══════════════════════════════════════════════════════════════════════════════
📊 GENIE RESULT
═══════════════════════════════════════════════════════════════════════════════
{genie_result}

═══════════════════════════════════════════════════════════════════════════════

Validate this result:"""

        try:
            response = llm.invoke([SystemMessage(content=validation_prompt)])
            validation_content = response.content
            logger.info(f"Validation Result:\n{validation_content}")

            # Parse validation
            if "VALIDATION: PASSED" in validation_content.upper():
                logger.info("✓ Result validation PASSED")
                return {
                    **state,
                    "messages": [AIMessage(content=f"Result Validation:\n{validation_content}")],
                    "result_validated": True,
                    "validation_passed": True,
                    "validation_analysis": validation_content,
                    "iterations": iterations + 1
                }
            else:
                logger.warning("✗ Result validation FAILED")
                return {
                    **state,
                    "messages": [AIMessage(content=f"Result Validation:\n{validation_content}")],
                    "result_validated": True,
                    "validation_passed": False,
                    "validation_analysis": validation_content,
                    "iterations": iterations + 1
                }

        except Exception as e:
            logger.error(f"Result validation failed: {e}", exc_info=True)
            return {
                **state,
                "result_validated": False,
                "validation_passed": False,
                "iterations": iterations + 1
            }

    return validate_result


# ============================================================================
# FOLLOW-UP GENERATION AGENT
# ============================================================================

def create_followup_generator(llm):
    """
    Agent that generates intelligent follow-up questions for deeper analysis.

    This helps users:
    - Discover additional insights
    - Compare with other dimensions
    - Identify trends and patterns
    - Perform root cause analysis
    """

    def generate_followups(state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("=== Follow-up Generation Agent ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Get original question
        original_question = state.get("original_question", "")

        # Get result summary
        result_summary = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and any(keyword in msg.content for keyword in ["Result", "Genie", "Answer"]):
                result_summary = msg.content[:500]  # Truncate for brevity
                break

        # Get schema info for context
        schema_info = state.get("schema_info", "")
        schema_snippet = schema_info[:1000] if schema_info else "Schema info not available"

        if not original_question or not result_summary:
            logger.warning("Cannot generate follow-ups - missing question or result")
            return {
                **state,
                "followups_generated": False,
                "followup_questions": [],
                "iterations": iterations + 1
            }

        # Follow-up generation prompt
        followup_prompt = f"""You are an analytical insights specialist.

Your task: Generate 3-5 intelligent follow-up questions to deepen the analysis.

═══════════════════════════════════════════════════════════════════════════════
🎯 FOLLOW-UP QUESTION PRINCIPLES
═══════════════════════════════════════════════════════════════════════════════

**Good Follow-ups:**
1. **Comparative Analysis:**
   - Compare with other dimensions (cities, time periods, categories)
   - Example: After "bangalore sentiment" → "Compare bangalore sentiment with delhi"

2. **Temporal Trends:**
   - Look at trends over time
   - Example: After "Q4 conversion rate" → "Show conversion rate trend for last 4 quarters"

3. **Drill-down:**
   - Break down aggregate metrics
   - Example: After "total revenue" → "Show revenue breakdown by product category"

4. **Root Cause Analysis:**
   - Investigate why something is happening
   - Example: After "low sentiment" → "What products have lowest sentiment scores?"

5. **Correlation Analysis:**
   - Explore relationships between metrics
   - Example: After "sentiment score" → "Is there correlation between sentiment and sales?"

**Must be Answerable:**
- Only suggest follow-ups that can be answered with available data
- Reference available tables and columns
- Don't suggest impossible queries

═══════════════════════════════════════════════════════════════════════════════
📋 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

**Follow-up 1:** [Question]
**Rationale:** [Why this follow-up provides value]
**Required Data:** [Tables/columns needed]

**Follow-up 2:** [Question]
**Rationale:** [Why this follow-up provides value]
**Required Data:** [Tables/columns needed]

**Follow-up 3:** [Question]
**Rationale:** [Why this follow-up provides value]
**Required Data:** [Tables/columns needed]

(Continue for 3-5 follow-ups)

═══════════════════════════════════════════════════════════════════════════════
📚 AVAILABLE DATA (Reference)
═══════════════════════════════════════════════════════════════════════════════
{schema_snippet}

═══════════════════════════════════════════════════════════════════════════════
❓ ORIGINAL QUESTION
═══════════════════════════════════════════════════════════════════════════════
{original_question}

═══════════════════════════════════════════════════════════════════════════════
📊 RESULT SUMMARY
═══════════════════════════════════════════════════════════════════════════════
{result_summary}

═══════════════════════════════════════════════════════════════════════════════

Generate analytical follow-up questions:"""

        try:
            response = llm.invoke([SystemMessage(content=followup_prompt)])
            followup_content = response.content
            logger.info(f"Follow-ups Generated:\n{followup_content}")

            # Extract follow-up questions
            followup_questions = []
            lines = followup_content.split("\n")
            for line in lines:
                if line.startswith("**Follow-up"):
                    # Extract question text
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        question_text = parts[1].strip().rstrip("*").strip()
                        followup_questions.append(question_text)

            logger.info(f"✓ Generated {len(followup_questions)} follow-up questions")

            return {
                **state,
                "messages": [AIMessage(content=f"Analytical Follow-ups:\n{followup_content}")],
                "followups_generated": True,
                "followup_questions": followup_questions,
                "followup_analysis": followup_content,
                "iterations": iterations + 1
            }

        except Exception as e:
            logger.error(f"Follow-up generation failed: {e}", exc_info=True)
            return {
                **state,
                "followups_generated": False,
                "followup_questions": [],
                "iterations": iterations + 1
            }

    return generate_followups


# ============================================================================
# ENHANCED SCHEMA ANALYSIS AGENT (Stricter Assumptions)
# ============================================================================

def create_strict_schema_analyzer(schema_reader, llm):
    """
    Enhanced schema analysis agent with STRICT rules against assumptions.

    Key differences from original:
    1. NEVER assumes default cities - always asks if missing
    2. NEVER assumes time ranges - always asks if ambiguous
    3. NEVER proceeds with partial information
    4. ALWAYS validates filters are explicit
    """

    def strict_schema_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("=== Strict Schema Analysis Agent ===")

        iterations = state.get("iterations", 0)
        messages = state["messages"]

        # Collect ALL user messages
        all_user_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                all_user_messages.append(msg.content)

        if not all_user_messages:
            logger.error("No user messages found")
            return {
                **state,
                "next_agent": "human",
                "is_answerable": False,
                "needs_clarification": True,
                "schema_analyzed": False,
                "iterations": iterations + 1
            }

        # Get or store original question
        original_question = state.get("original_question", "")
        if not original_question:
            original_question = all_user_messages[0]

        # Build user context
        if len(all_user_messages) > 1:
            user_question = f"""Original question: {original_question}

Additional clarification provided by user: {all_user_messages[-1]}

IMPORTANT: The user has now provided additional details. Re-analyze with this NEW information."""
        else:
            user_question = original_question

        # Read schemas if not in state
        schema_info = state.get("schema_info", "")
        if not schema_info:
            logger.info("Reading Unity Catalog schemas...")
            schema_info = schema_reader.read_all_configured_schemas()

        # Get RAG context
        rag_context = state.get("rag_context", "")

        # STRICT analysis prompt - NO ASSUMPTIONS
        analysis_prompt = f"""You are an expert data analyst with STRICT rules against making assumptions.

Your task: Determine if the user's question can be answered, but NEVER make assumptions.

═══════════════════════════════════════════════════════════════════════════════
🚫 CRITICAL RULES - NEVER VIOLATE THESE
═══════════════════════════════════════════════════════════════════════════════

**RULE 1: NO DEFAULT CITIES**
❌ User asks "show sentiment" (no city) → DO NOT assume "all cities" or pick one
✅ User asks "show sentiment" → ASK: "For which city or region?"

**RULE 2: NO DEFAULT TIME RANGES**
❌ User asks "show sales last month" (no year) → DO NOT assume current year
✅ User asks "show sales last month" → ASK: "Which year's last month?"

❌ User asks "Q4 data" (no year) → DO NOT assume most recent
✅ User asks "Q4 data" → ASK: "Q4 of which year?"

**RULE 3: NO PARTIAL ANSWERS**
❌ User asks "sentiment for bangalore and delhi" → DO NOT answer just for bangalore
✅ User asks "sentiment for bangalore and delhi" → Answer for BOTH or ask for clarification

**RULE 4: EXPLICIT FILTERS ONLY**
❌ User says "sentiment" and city column exists → DO NOT filter by any city
✅ User says "sentiment for bangalore" → Filter by city = 'bangalore'

**RULE 5: STRICT MATCHING**
❌ User asks for "delhi" → DO NOT return results for other cities
✅ User asks for "delhi" → ONLY return delhi results

═══════════════════════════════════════════════════════════════════════════════
📊 ANALYSIS DECISION TREE
═══════════════════════════════════════════════════════════════════════════════

**ANSWERABLE: YES** - ONLY if ALL of these are true:
✓ All required columns exist
✓ All filters are explicitly provided by user
✓ No ambiguity in time ranges
✓ No ambiguity in locations
✓ Question is clear and complete

**ANSWERABLE: NEEDS_CLARIFICATION** - If ANY of these are true:
? Location mentioned but ambiguous ("show me data" - for which city?)
? Time range mentioned but incomplete ("last month" - which year?)
? Multiple valid interpretations ("satisfaction" - NPS, CSAT, or sentiment?)
? Missing critical filter (user says "sentiment" but doesn't specify city)

**ANSWERABLE: NO** - ONLY if:
✗ Required columns don't exist at all
✗ Calculation is impossible with available data
✗ Question is about data we don't have

═══════════════════════════════════════════════════════════════════════════════
🔍 SEMANTIC COLUMN MATCHING (Same as before)
═══════════════════════════════════════════════════════════════════════════════

User says "sentiment" → Think: sentiment_score, customer_satisfaction, nps, csat
User says "conversion" → Think: conversion_rate, conversion_count, visitor_count
User says "location" → Think: city, region, location, geography

═══════════════════════════════════════════════════════════════════════════════
💡 RAG INTEGRATION
═══════════════════════════════════════════════════════════════════════════════
{f'''📚 BUSINESS CONTEXT FROM DOCUMENTATION:
{rag_context}

Use this to understand column definitions and business rules.''' if rag_context else ""}

═══════════════════════════════════════════════════════════════════════════════
📁 AVAILABLE SCHEMAS
═══════════════════════════════════════════════════════════════════════════════
{schema_info}

═══════════════════════════════════════════════════════════════════════════════
❓ USER QUESTION
═══════════════════════════════════════════════════════════════════════════════
{user_question}

═══════════════════════════════════════════════════════════════════════════════
📋 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

**ANSWERABLE: YES** / **ANSWERABLE: NEEDS_CLARIFICATION** / **ANSWERABLE: NO**

**INTELLIGENT REASONING:**
[Your thought process - what is missing or what is clear]

**SELECTED COLUMNS AND TABLES:**
[If answerable, list exact columns needed]

**WHAT'S NEEDED FROM USER:**
[If clarification needed, list SPECIFIC missing information - be VERY specific!]

**CLARIFICATION QUESTIONS (if needed):**
[Ask SPECIFIC questions, not generic ones. Examples:
 ✓ "For which city would you like to see sentiment scores? Available: bangalore, delhi, mumbai"
 ✓ "Q4 of which year? 2023 or 2024?"
 ✗ "Can you provide more details?" (too vague)]

═══════════════════════════════════════════════════════════════════════════════

Analyze with STRICT adherence to the rules - NO ASSUMPTIONS ALLOWED:"""

        try:
            response = llm.invoke([SystemMessage(content=analysis_prompt)])
            analysis_content = response.content
            logger.info(f"Strict Schema Analysis:\n{analysis_content}")

            # Parse result (same logic as before)
            content_upper = analysis_content.upper()

            if "ANSWERABLE: NEEDS_CLARIFICATION" in content_upper or "NEEDS CLARIFICATION" in content_upper:
                logger.info("⚠️  Question needs clarification")

                clarification = "I need more information to answer your question."
                if "CLARIFICATION QUESTIONS:" in analysis_content:
                    parts = analysis_content.split("CLARIFICATION QUESTIONS:")
                    if len(parts) > 1:
                        clarification = parts[1].strip()

                clarification_msg = f"""[Strict Schema Analysis - Needs Clarification]

I found data that could answer your question, but I need specific information to avoid making assumptions:

{clarification}

⚠️  **Important:** I will NOT assume default values for cities, time ranges, or other filters."""

                return {
                    **state,
                    "messages": [AIMessage(content=clarification_msg)],
                    "original_question": original_question,
                    "schema_info": schema_info,
                    "schema_analyzed": True,
                    "is_answerable": False,
                    "needs_clarification": True,
                    "next_agent": "human",
                    "iterations": iterations + 1
                }

            elif "ANSWERABLE: YES" in content_upper:
                logger.info("✓ Question is answerable with explicit information")
                return {
                    **state,
                    "messages": [AIMessage(content=f"Strict Schema Analysis:\n{analysis_content}")],
                    "original_question": original_question,
                    "schema_info": schema_info,
                    "schema_analyzed": True,
                    "is_answerable": True,
                    "needs_clarification": False,
                    "next_agent": "query_planner",
                    "iterations": iterations + 1
                }

            else:  # ANSWERABLE: NO
                logger.info("✗ Question is NOT answerable")

                reason = "This question cannot be answered with the available data."
                if "REASONING:" in analysis_content:
                    parts = analysis_content.split("REASONING:")
                    if len(parts) > 1:
                        reason = parts[1].split("**")[0].strip()

                return {
                    **state,
                    "messages": [AIMessage(content=f"I'm sorry, but {reason}")],
                    "original_question": original_question,
                    "schema_info": schema_info,
                    "schema_analyzed": True,
                    "is_answerable": False,
                    "needs_clarification": False,
                    "next_agent": "human",
                    "iterations": iterations + 1
                }

        except Exception as e:
            logger.error(f"Strict schema analysis failed: {e}", exc_info=True)
            return {
                **state,
                "messages": [AIMessage(content=f"Schema analysis error: {str(e)}")],
                "schema_analyzed": False,
                "next_agent": "human",
                "is_answerable": False,
                "iterations": iterations + 1
            }

    return strict_schema_analysis
