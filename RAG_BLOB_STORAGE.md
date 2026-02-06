# 📁 RAG Azure Blob Storage Integration

**Date:** 2026-02-06
**Version:** 2.2.0
**Priority:** CRITICAL for production RAG deployment

---

## ✅ WHAT CHANGED

### Issue: RAG Was Using Local Filesystem
**Problem:** RAG agent was monitoring a local directory (`RAG_WATCH_PATH=/path/to/watch/folder`), which doesn't work in containerized/distributed environments.

**Impact:**
- ❌ Files uploaded locally on one container not visible to others
- ❌ Data loss when containers restart
- ❌ Not scalable for production
- ❌ Manual file management required

**Solution:** ✅ **RAG now monitors Azure Blob Storage container automatically**

---

## 🏗️ NEW ARCHITECTURE

### Before (Local Filesystem)
```
User → Uploads file to local path /app/data/rag_documents/
         ↓
      Watchdog monitors local directory
         ↓
      File processed by RAG agent
         ↓
      ❌ File only visible to this container
      ❌ Lost on container restart
```

### After (Azure Blob Storage)
```
User → Uploads file to Azure Blob Storage container "agent-rag-docs"
         ↓
      BlobMonitorService polls container every 10s
         ↓
      New blob detected → Downloads to temp
         ↓
      RAG agent processes file
         ↓
      Embeddings stored in vector store (also in Azure Blob!)
         ↓
      ✅ Available to all containers
      ✅ Persists forever
      ✅ Scalable
```

---

## 🔧 WHAT WAS IMPLEMENTED

### 1. New BlobMonitorService (`src/services/blob_monitor.py`)

**Purpose:** Monitors Azure Blob Storage container for new/modified files

**Key Features:**
- Polls Azure Blob container every N seconds (configurable)
- Detects new blobs and modified blobs
- Downloads blob to temp directory
- Triggers RAG processing callback
- Tracks processed blobs to avoid duplicates

**How It Works:**
```python
class BlobMonitorService:
    def _poll_blobs(self):
        # List blobs in container
        blobs = self.storage.list_blobs(container, prefix)

        for blob in blobs:
            # Check if new or modified
            if blob not in processed or blob.last_modified > processed[blob]:
                # Download and process
                self._process_blob(blob)

    def _process_blob(self, blob_name):
        # Download to temp
        blob_data = storage.download_blob(container, blob_name)

        # Save to temp file
        temp_file = f"/tmp/rag_blobs/{filename}"
        write(temp_file, blob_data)

        # Trigger RAG callback
        on_file_callback(temp_file)
```

---

### 2. Updated Azure Blob Storage Service (`src/services/storage.py`)

**Enhancement:** `list_blobs()` now returns metadata (not just names)

**Before:**
```python
blobs = storage.list_blobs("container")
# Returns: ["file1.pdf", "file2.docx"]
```

**After:**
```python
blobs = storage.list_blobs("container")
# Returns: [
#   {"name": "file1.pdf", "last_modified": datetime(...), "size": 12345},
#   {"name": "file2.docx", "last_modified": datetime(...), "size": 67890}
# ]
```

**Added:** `get_blob_storage()` alias for consistency

---

### 3. Updated Configuration (`src/core/config.py`)

**RAGConfig Changes:**
```python
class RAGConfig(BaseSettings):
    # DEPRECATED - no longer used
    watch_path: Optional[str] = Field(default=None, alias="RAG_WATCH_PATH")

    # NEW - how often to poll Azure Blob Storage
    poll_interval: int = Field(default=10, alias="RAG_POLL_INTERVAL")  # seconds

    # Existing
    auto_process: bool = Field(default=True, alias="RAG_AUTO_PROCESS")
    supported_extensions: List[str] = [".pdf", ".txt", ".csv", ...]
```

---

### 4. Updated Environment Configuration (`.env.example`)

**Key Changes:**
```bash
# ----------------------------------------------------------------------------
# RAG File Monitoring
# IMPORTANT: RAG monitors Azure Blob Storage container (not local filesystem).
# Upload files to the RAG container and they'll be automatically processed.
# ----------------------------------------------------------------------------
# RAG_WATCH_PATH is not used (deprecated - was for local filesystem monitoring)
# Files are monitored in the AZURE_STORAGE_CONTAINER_RAG container above
RAG_AUTO_PROCESS=true
RAG_SUPPORTED_EXTENSIONS=.pdf,.txt,.csv,.docx,.pptx,.xlsx
RAG_POLL_INTERVAL=10  # How often to check for new blobs (seconds)
```

**Also Added - .env Format Guide:**
```bash
# IMPORTANT: For comma-separated lists, do NOT use quotes around individual items!
# CORRECT:   UNITY_CATALOG_TABLES=table1,table2,table3
# WRONG:     UNITY_CATALOG_TABLES='table1','table2','table3'  ← Quotes in value!
```

---

## 🚀 HOW TO USE

### Step 1: Configure Azure Blob Storage

**.env:**
```bash
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=your-account;AccountKey=your-key;EndpointSuffix=core.windows.net
AZURE_STORAGE_CONTAINER_RAG=agent-rag-docs
RAG_POLL_INTERVAL=10  # Check for new files every 10 seconds
```

---

### Step 2: Upload Documents to Azure Blob

**Option A: Azure Portal**
1. Go to Azure Portal → Storage Account → Containers
2. Click on `agent-rag-docs` container
3. Click "Upload"
4. Select your PDF/DOCX/CSV files
5. Upload

**Option B: Azure CLI**
```bash
az storage blob upload \
  --container-name agent-rag-docs \
  --file document.pdf \
  --name document.pdf \
  --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

**Option C: Python Code**
```python
from src.services.storage import get_blob_storage

storage = get_blob_storage()
with open("document.pdf", "rb") as f:
    storage.upload_blob(
        container_name="agent-rag-docs",
        blob_name="document.pdf",
        data=f.read(),
        serialize="text"  # Raw bytes
    )
```

**Option D: Azure Storage Explorer**
- Download Azure Storage Explorer
- Connect to your storage account
- Drag and drop files to `agent-rag-docs` container

---

### Step 3: Automatic Processing

**What Happens Automatically:**
```
1. BlobMonitorService polls container every 10s
2. Detects new blob: "document.pdf"
3. Downloads to temp: /tmp/rag_blobs/document.pdf
4. Triggers RAG agent callback
5. RAG agent:
   - Parses PDF
   - Chunks text (1000 chars, 200 overlap)
   - Generates embeddings
   - Stores in vector store (also Azure Blob!)
6. Document ready for queries!
```

**Timeline:**
- Upload file → Within 10 seconds → Detected and processed
- Total processing time: ~10-30 seconds depending on file size

---

### Step 4: Verify Processing

**Check Logs:**
```bash
tail -f logs/app.log | grep "New blob detected"

# Expected output:
# {"level": "INFO", "message": "New blob detected", "blob": "document.pdf"}
# {"level": "INFO", "message": "Downloaded blob to temp file", "blob": "document.pdf"}
# {"level": "INFO", "message": "Processed document", "file": "document.pdf"}
```

**Check Vector Store:**
```python
from src.services.vector_store import get_vector_store

rag_store = get_vector_store("rag_docs")
stats = rag_store.get_stats()
print(stats)
# Should show document count increased
```

---

## 📊 COMPARISON

| Feature | Before (Local FS) | After (Azure Blob) | Improvement |
|---------|-------------------|-------------------|-------------|
| **Upload Method** | Manual to container | Azure Portal/CLI/API | Easier |
| **Multi-Instance** | ❌ No | ✅ Yes | Scalable |
| **Data Persistence** | ❌ Lost on restart | ✅ Permanent | Production-ready |
| **File Sharing** | ❌ Single container | ✅ All containers | Distributed |
| **Detection Delay** | Instant (Watchdog) | ~10s (polling) | Acceptable |
| **Management** | Manual file copy | Azure Blob UI | Professional |

---

## ⚙️ CONFIGURATION OPTIONS

### Poll Interval Tuning

**.env:**
```bash
# Fast detection (higher Azure API costs)
RAG_POLL_INTERVAL=5  # Check every 5 seconds

# Balanced (recommended)
RAG_POLL_INTERVAL=10  # Check every 10 seconds

# Slower (lower costs, delayed detection)
RAG_POLL_INTERVAL=30  # Check every 30 seconds
```

**Cost Impact:**
- 10s interval = 6 API calls/minute = 360 calls/hour = $0.01/hour
- 30s interval = 2 API calls/minute = 120 calls/hour = $0.003/hour

---

### Supported File Types

**.env:**
```bash
# Default supported extensions
RAG_SUPPORTED_EXTENSIONS=.pdf,.txt,.csv,.docx,.pptx,.xlsx

# Add more types
RAG_SUPPORTED_EXTENSIONS=.pdf,.txt,.csv,.docx,.pptx,.xlsx,.md,.json

# Restrict to specific types
RAG_SUPPORTED_EXTENSIONS=.pdf,.docx
```

---

## 🔄 MIGRATION GUIDE

### If Upgrading from Local Filesystem RAG

#### Option A: Start Fresh (Recommended)
```bash
# 1. Update .env
# Remove or comment out RAG_WATCH_PATH
# RAG_WATCH_PATH=/path/to/watch  # ← Deprecated

# Add RAG_POLL_INTERVAL
RAG_POLL_INTERVAL=10

# 2. Upload documents to Azure Blob
az storage blob upload-batch \
  --destination agent-rag-docs \
  --source /path/to/old/documents \
  --connection-string "$AZURE_STORAGE_CONNECTION_STRING"

# 3. Start application
# Documents will auto-process within 10s each
```

#### Option B: Manual Upload
```python
from pathlib import Path
from src.services.storage import get_blob_storage

storage = get_blob_storage()
local_path = Path("/path/to/old/documents")

for file in local_path.glob("*.pdf"):
    with open(file, "rb") as f:
        storage.upload_blob(
            container_name="agent-rag-docs",
            blob_name=file.name,
            data=f.read(),
            serialize="text"
        )
    print(f"Uploaded {file.name}")
```

---

## 🐛 TROUBLESHOOTING

### Issue: "Blobs not being detected"

**Cause:** BlobMonitorService not started

**Solution:**
```python
from src.agents.rag_agent import get_rag_agent

rag_agent = get_rag_agent()
# Blob monitor starts automatically in RAG agent initialization

# Or start manually:
from src.services.blob_monitor import get_blob_monitor
monitor = get_blob_monitor()
monitor.start()
```

---

### Issue: "Azure Blob connection failed"

**Cause:** Invalid connection string

**Solution:**
```bash
# Verify connection string in .env
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

# Test connection
python -c "
from src.services.storage import get_blob_storage
storage = get_blob_storage()
print('✅ Connected')
"
```

---

### Issue: "Files processed multiple times"

**Cause:** Poll interval too short + processing takes longer than interval

**Solution:**
```bash
# Increase poll interval
RAG_POLL_INTERVAL=30  # or 60
```

---

### Issue: "High Azure API costs"

**Cause:** Poll interval too short

**Solution:**
```bash
# Reduce polling frequency
RAG_POLL_INTERVAL=30  # or 60

# Or use Azure Event Grid (advanced)
# Event Grid can push notifications instead of polling
```

---

## ✅ PRODUCTION CHECKLIST

Before deploying RAG with Azure Blob:

- [ ] Azure Blob Storage connection string configured
- [ ] `agent-rag-docs` container exists (auto-created)
- [ ] `RAG_POLL_INTERVAL` set appropriately (10-30s)
- [ ] `RAG_SUPPORTED_EXTENSIONS` includes your file types
- [ ] Tested blob upload via Azure Portal
- [ ] Verified blob detection in logs
- [ ] Confirmed vector store gets populated
- [ ] Tested query retrieval from uploaded docs
- [ ] Removed old `RAG_WATCH_PATH` from .env

---

## 📝 CODE EXAMPLES

### Start Blob Monitoring

```python
from src.services.blob_monitor import get_blob_monitor

def process_document(file_path: str):
    print(f"Processing: {file_path}")
    # Your RAG processing logic

monitor = get_blob_monitor(on_file_callback=process_document)
monitor.start()

# Monitor runs in background thread
```

---

### Upload File Programmatically

```python
from src.services.storage import get_blob_storage

storage = get_blob_storage()

# Upload PDF
with open("report.pdf", "rb") as f:
    storage.upload_blob(
        container_name="agent-rag-docs",
        blob_name="reports/report.pdf",  # Can use paths!
        data=f.read(),
        serialize="text"
    )

print("✅ Uploaded! Will be processed within 10s")
```

---

### List Uploaded Documents

```python
from src.services.storage import get_blob_storage

storage = get_blob_storage()

blobs = storage.list_blobs("agent-rag-docs")
for blob in blobs:
    print(f"{blob['name']} - {blob['size']} bytes - {blob['last_modified']}")
```

---

### Monitor Stats

```python
from src.services.blob_monitor import get_blob_monitor

monitor = get_blob_monitor()
stats = monitor.get_stats()

print(f"Container: {stats['container']}")
print(f"Poll interval: {stats['poll_interval']}s")
print(f"Processed blobs: {stats['processed_blobs']}")
print(f"Running: {stats['is_running']}")
```

---

## 🎯 SUMMARY

### Before
- ❌ RAG monitored local filesystem
- ❌ Files manually copied to containers
- ❌ Data lost on restart
- ❌ Not scalable

### After
- ✅ RAG monitors Azure Blob Storage
- ✅ Upload via Azure Portal/CLI/API
- ✅ Data persists forever
- ✅ Horizontally scalable
- ✅ Production-ready

### Key Benefits
1. **Upload Anywhere** - Azure Portal, CLI, API, Storage Explorer
2. **Process Automatically** - Detected within 10s
3. **Scale Horizontally** - Multiple containers share same blob storage
4. **Never Lose Data** - Blobs persist in Azure
5. **Professional Management** - Azure Blob UI, lifecycle policies, etc.

---

## 🔗 RELATED FIXES

This update is part of the production storage improvements:
1. **Vector stores** → Azure Blob Storage (`PRODUCTION_FIXES.md`)
2. **MLflow tracking** → Databricks workspace (`PRODUCTION_FIXES.md`)
3. **RAG documents** → Azure Blob Storage (this document)

**All persistent data now in Azure - fully production-ready!** ✅

---

**Version:** 2.2.0
**Date:** 2026-02-06
**Status:** ✅ PRODUCTION-READY

---

*Upload documents to Azure Blob Storage container `agent-rag-docs` and they'll be automatically processed within 10 seconds!*
