# RAG and Smart Caching Architecture Design

**Version:** 5.1.0
**Date:** 2026-02-12
**Purpose:** Add production-ready RAG and SQL caching to v5.0 bulletproof system

---

## 🎯 Real-World Use Cases

### Use Case 1: RAG-Assisted Schema Understanding
**Scenario:** User asks ambiguous question about data they don't fully understand

```
User: "Show me customer satisfaction metrics"

Without RAG:
❌ Schema analysis: "Which table? We have 15 tables..."
❌ User: "I don't know, what do we have?"
❌ Back and forth...

With RAG:
✅ RAG searches documentation embeddings
✅ Finds: "Customer satisfaction tracked in nps_score, sentiment_analysis, csat_survey"
✅ Schema analysis: "I found 3 tables with customer satisfaction data..."
✅ User: "Use nps_score"
✅ Proceeds efficiently
```

### Use Case 2: Smart SQL Caching
**Scenario:** Multiple users asking similar questions

```
User 1 (10:00 AM): "What's total revenue in Q4 2024?"
→ Genie executes SQL → Returns $1.2M → Cached with embedding

User 2 (10:15 AM): "Show me Q4 2024 revenue totals"
→ Semantic similarity: 0.95 (very similar!)
→ Cache hit! Returns $1.2M (no Genie call)
→ Saves: 3-5 seconds + API costs

User 3 (11:00 AM): "Q4 2024 revenue?"
→ Cache hit! Returns $1.2M
→ Saves: 3-5 seconds + API costs

Benefits:
- Faster responses (cache hit: <100ms vs Genie: 3-5s)
- Lower costs (no redundant Genie API calls)
- Consistent answers (same data for similar queries)
```

### Use Case 3: RAG + Cache Combined
**Scenario:** New employee asking questions

```
User: "What customer sentiment data do we have for bangalore?"

Step 1: RAG Agent
→ Searches documentation
→ Finds: "Sentiment data in sentiment_score column, city in location"
→ Provides context to schema analysis

Step 2: Schema Analysis (with RAG context)
→ Uses RAG hints to quickly identify correct table
→ Determines answerable

Step 3: Query Planning
→ Creates: "Show sentiment for bangalore from sentiment_table"

Step 4: Cached Genie Execution
→ Check cache with query embedding
→ Cache miss (first time)
→ Execute Genie
→ Cache result (TTL: 1 hour)

Step 5: Future queries benefit
→ Anyone asking similar questions gets cached results
```

---

## 🏗️ Architecture Design

### Updated Workflow

```
User Question
    ↓
Supervisor
    ↓
    ├─→ RAG Agent (if docs exist)
    │   └─→ Search documentation embeddings
    │       └─→ Return context hints
    ↓
Schema Analysis (with RAG context)
    ↓
    ├─→ Answerable? → Query Planner
    │                      ↓
    │                  Cached Genie (smart cache layer)
    │                      ↓
    │                      ├─→ Check cache (semantic similarity)
    │                      │   └─→ Hit? Return cached result
    │                      │   └─→ Miss? Execute Genie + cache result
    │                      ↓
    │                  Synthesis
    │
    ├─→ Needs Clarification? → Human → Supervisor
    │
    └─→ Not Answerable? → Synthesis
```

### Agent Nodes

1. **RAG Agent** (NEW)
   - **Input:** User question
   - **Process:**
     - Search document embeddings (FAISS)
     - Find relevant documentation
     - Extract table/column hints
   - **Output:** RAG context string
   - **Optional:** Only runs if documents exist

2. **Schema Analysis** (UPDATED)
   - **Input:** User question + RAG context
   - **Process:**
     - Use RAG hints to narrow search
     - Semantic matching with Unity Catalog
     - Determine answerability
   - **Output:** Schema info + answerable status

3. **Query Planner** (UNCHANGED)
   - Creates natural language queries for Genie

4. **Cached Genie** (UPDATED)
   - **Input:** Formatted query
   - **Process:**
     - Generate query embedding
     - Check cache (similarity > 0.90)
     - If hit: Return cached result
     - If miss: Execute Genie + cache result
   - **Output:** Query results
   - **Cache:** In-memory dict (upgradable to Redis)

5. **Synthesis** (UNCHANGED)
   - Synthesizes final answer

---

## 📦 Components to Implement

### 1. Embeddings Service (`src/utils/embeddings.py`)

```python
class EmbeddingService:
    """Azure OpenAI embeddings for RAG and caching"""

    def __init__(self, azure_client):
        self.client = azure_client
        self.cache = {}  # In-memory cache for embeddings

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        # Check cache first
        # Call Azure OpenAI embeddings API
        # Return 1536-dim vector

    def similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Cosine similarity between embeddings"""
        # Calculate cosine similarity
```

### 2. Document Parser (`src/utils/parsers.py`)

```python
class DocumentParser:
    """Parse documents for RAG ingestion"""

    def parse(self, file_path: str) -> Document:
        """Parse document based on extension"""
        # Support: .txt, .md, .pdf, .docx
        # Extract text + metadata
        # Return Document object

    def chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Chunk large documents"""
        # Split into chunks with overlap
        # Preserve sentence boundaries
```

### 3. RAG Store (`src/services/rag_store.py`)

```python
class RAGStore:
    """Vector store for document embeddings"""

    def __init__(self, embedding_service, vector_store_path):
        self.embeddings = embedding_service
        self.store = FAISS.load(vector_store_path) or FAISS.create()

    def add_documents(self, documents: List[Document]):
        """Add documents to vector store"""
        # Generate embeddings
        # Add to FAISS index
        # Save to disk

    def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Semantic search for relevant documents"""
        # Generate query embedding
        # Search FAISS index
        # Return top_k most similar documents
```

### 4. Smart Cache (`src/services/smart_cache.py`)

```python
class SmartSQLCache:
    """Semantic cache for SQL query results"""

    def __init__(self, embedding_service, ttl_seconds: int = 3600):
        self.embeddings = embedding_service
        self.cache = {}  # {embedding_key: (result, timestamp)}
        self.ttl = ttl_seconds
        self.similarity_threshold = 0.90

    def get(self, query: str) -> Optional[str]:
        """Get cached result if similar query exists"""
        # Generate query embedding
        # Find most similar cached query
        # If similarity > threshold and not expired: return result
        # Else: return None

    def set(self, query: str, result: str):
        """Cache query result"""
        # Generate query embedding
        # Store: {embedding: (result, timestamp)}
        # Prune expired entries

    def clear_expired(self):
        """Remove expired cache entries"""
        # Check timestamps
        # Delete entries older than TTL
```

---

## 📊 Updated State Schema

```python
class AgentState(TypedDict):
    # Existing fields
    messages: Annotated[list[BaseMessage], operator.add]
    schema_analyzed: bool
    query_planned: bool
    genie_executed: bool
    original_question: str
    schema_info: str
    formatted_query: str
    final_answer: str
    next_agent: str
    iterations: int
    is_answerable: bool
    needs_clarification: bool
    clarification_provided: bool

    # NEW: RAG fields
    rag_checked: bool          # RAG search completed
    rag_context: str           # RAG findings (table hints, context)
    rag_documents: list        # Retrieved documents (optional)

    # NEW: Caching fields
    cache_hit: bool            # Query served from cache
    cache_key: str             # Cache key for this query
```

---

## 🔄 Updated Routing Logic

```python
def supervisor_node(state):
    # Existing routing logic...

    # NEW: RAG routing (if documents exist and not yet checked)
    if not state.get("rag_checked", False) and has_rag_documents():
        return {**state, "next_agent": "rag"}

    # Schema analysis (with RAG context if available)
    if not state.get("schema_analyzed", False):
        return {**state, "next_agent": "schema"}

    # Rest of routing unchanged...
```

---

## 📝 Configuration

```python
# RAG Configuration
RAG_ENABLED=true
RAG_DOCUMENTS_PATH=./data/documents
RAG_VECTOR_STORE_PATH=./data/vector_stores/rag_index
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
RAG_TOP_K=3

# Cache Configuration
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
CACHE_SIMILARITY_THRESHOLD=0.90
CACHE_MAX_ENTRIES=1000
CACHE_TYPE=memory  # memory or redis
```

---

## 🚀 Implementation Plan

### Phase 1: Embeddings Foundation
1. Create `src/utils/embeddings.py`
2. Test with Azure OpenAI embeddings API
3. Add caching layer for embeddings

### Phase 2: Document Processing
1. Create `src/utils/parsers.py`
2. Support .txt, .md, .pdf, .docx
3. Test document parsing and chunking

### Phase 3: RAG Store
1. Create `src/services/rag_store.py`
2. Integrate FAISS vector store
3. Document ingestion pipeline
4. Semantic search

### Phase 4: RAG Agent Node
1. Add RAG node to LangGraph
2. State fields for RAG
3. Routing logic
4. Integration with schema analysis

### Phase 5: Smart Cache
1. Create `src/services/smart_cache.py`
2. Semantic similarity matching
3. TTL management
4. Wrap Genie node with cache layer

### Phase 6: Integration & Testing
1. Update supervisor routing
2. Update AgentState
3. End-to-end testing
4. Performance benchmarking

### Phase 7: Documentation
1. Update SIMPLIFIED_V5.md
2. Add RAG setup guide
3. Add caching configuration guide

---

## 📈 Expected Benefits

### Performance
- **Cache hit ratio:** 30-50% for typical workloads
- **Response time:**
  - Cache hit: <100ms (vs 3-5s Genie)
  - 10x faster for cached queries
- **Cost savings:**
  - 30-50% reduction in Genie API calls
  - Significant savings on high-traffic applications

### User Experience
- **Faster answers:** Cached queries return instantly
- **Better guidance:** RAG provides context for ambiguous questions
- **Fewer clarifications:** RAG helps schema analysis be smarter
- **Consistent results:** Same query always returns same cached result

### Operational
- **Lower API costs:** Fewer Genie calls
- **Better resource utilization:** Cache reduces backend load
- **Knowledge management:** RAG indexes documentation automatically
- **Audit trail:** Cache provides query history

---

## 🔧 Production Considerations

### RAG
- **Document updates:** Incremental indexing when docs change
- **Index size:** Monitor FAISS index size, prune if needed
- **Relevance:** Tune top_k and similarity thresholds
- **Security:** Ensure RAG only accesses authorized documents

### Caching
- **Memory management:** Set max_entries, implement LRU eviction
- **Cache invalidation:** Clear cache when underlying data changes
- **Distributed caching:** Use Redis for multi-instance deployments
- **Monitoring:** Track hit rate, miss rate, cache size

---

**Status:** Design Complete ✅
**Next:** Implementation Phase 1 - Embeddings Foundation
