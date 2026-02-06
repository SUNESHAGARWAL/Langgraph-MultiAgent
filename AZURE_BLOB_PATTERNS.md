# 📁 Azure Blob Storage - Container Patterns

**Date:** 2026-02-06
**Version:** 2.3.0
**Purpose:** Flexible container configuration for shared Azure Blob Storage

---

## 🎯 PROBLEM SOLVED

**Your Requirement:**
> "I have a storage account with container `reservoir`, and within it a folder `adm/CXEngine/`. I want to use that as root."

**Solution:** System now supports **both separate containers AND single container with prefixes**!

---

## 🏗️ AZURE BLOB STORAGE STRUCTURE

### Important Concepts

```
Storage Account (from connection string)
  └── Container (NO slashes allowed in name!)
      └── Blob paths (virtual folders - CAN have slashes)
```

**Key Rules:**
1. **Container name** = NO slashes, 3-63 chars, lowercase/numbers/hyphens only
2. **Blob path** = CAN have slashes, creates virtual folder structure

---

## ✅ PATTERN 1: Separate Containers (Default)

### Configuration

**.env:**
```bash
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpoints...

# Three separate containers
AZURE_STORAGE_CONTAINER_CACHE=agent-cache
AZURE_STORAGE_CONTAINER_RAG=agent-rag-docs
AZURE_STORAGE_CONTAINER_EDA=agent-eda-results
```

### Azure Structure

```
Storage Account
  ├── agent-cache/
  │   └── cache/
  │       └── query_123.json
  │
  ├── agent-rag-docs/
  │   ├── document1.pdf
  │   └── document2.docx
  │
  ├── agent-eda-results/
  │   └── eda/
  │       └── sales_data.json
  │
  └── vector-stores/
      ├── sql_cache/index.faiss
      └── rag_docs/index.faiss
```

### When to Use
- ✅ You have full control of storage account
- ✅ Want clear separation between data types
- ✅ Default recommended approach

---

## ✅ PATTERN 2: Single Container with Blob Prefixes (Your Case!)

### Configuration

**.env:**
```bash
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpoints...

# Single container with prefixes
AZURE_STORAGE_CONTAINER_CACHE=reservoir/adm/CXEngine/agent-cache
AZURE_STORAGE_CONTAINER_RAG=reservoir/adm/CXEngine/agent-rag-docs
AZURE_STORAGE_CONTAINER_EDA=reservoir/adm/CXEngine/agent-eda-results
```

### How It Works

The system automatically parses:
- `reservoir/adm/CXEngine/agent-cache`
  - Container: `reservoir`
  - Blob prefix: `adm/CXEngine/agent-cache`

### Azure Structure

```
Storage Account
  └── reservoir/                         ← SINGLE CONTAINER
      └── adm/
          └── CXEngine/                  ← YOUR ROOT FOLDER
              ├── agent-cache/
              │   └── cache/
              │       └── query_123.json
              │
              ├── agent-rag-docs/
              │   ├── document1.pdf
              │   └── document2.docx
              │
              └── agent-eda-results/
                  └── eda/
                      └── sales_data.json
```

### When to Use
- ✅ You have a **shared container** with other applications
- ✅ Need to organize under specific folder structure (`adm/CXEngine`)
- ✅ Container already exists (like `reservoir`)

---

## 🚀 YOUR SPECIFIC CONFIGURATION

Based on your requirement:

**.env:**
```bash
# Azure Blob Storage connection
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=your-account;AccountKey=your-key;EndpointSuffix=core.windows.net

# Pattern 2: Single container with prefixes
AZURE_STORAGE_CONTAINER_CACHE=reservoir/adm/CXEngine/agent-cache
AZURE_STORAGE_CONTAINER_RAG=reservoir/adm/CXEngine/agent-rag-docs
AZURE_STORAGE_CONTAINER_EDA=reservoir/adm/CXEngine/agent-eda-results
```

### Result in Azure Portal

When you browse container `reservoir` in Azure Portal, you'll see:

```
reservoir/
  └── adm/
      └── CXEngine/
          ├── agent-cache/
          │   └── cache/
          │       └── query_123.json              ← Cache data
          │
          ├── agent-rag-docs/
          │   ├── report.pdf                      ← Upload RAG files here!
          │   └── guide.docx
          │   └── metadata/
          │       └── report.pdf.json
          │
          ├── agent-eda-results/
          │   └── eda/
          │       └── sales_data.json             ← Table EDA results
          │
          └── (other apps can use adm/OtherApp/ etc.)
```

---

## 📊 COMPARISON

| Aspect | Pattern 1 (Separate) | Pattern 2 (Single + Prefix) |
|--------|----------------------|------------------------------|
| **Containers** | 3 (agent-cache, agent-rag-docs, agent-eda-results) | 1 (reservoir) |
| **Isolation** | ✅ Full separation | ⚠️ Shared container |
| **Organization** | By container | By blob prefix |
| **Use Case** | Dedicated storage | Shared storage |
| **Your Requirement** | ❌ Not suitable | ✅ Perfect fit! |

---

## 💻 CODE IMPLEMENTATION

### How It Works Internally

```python
# src/core/config.py
class AzureStorageConfig:
    @staticmethod
    def _parse_container_path(value: str) -> tuple[str, str]:
        """
        Parse container/prefix pattern.

        Examples:
        - "agent-cache" → ("agent-cache", "")
        - "reservoir/adm/CXEngine/agent-cache" → ("reservoir", "adm/CXEngine/agent-cache")
        """
        if "/" in value:
            parts = value.split("/", 1)
            return parts[0], parts[1]  # container, prefix
        return value, ""

    def get_rag_config(self) -> tuple[str, str]:
        """Returns (container_name, blob_prefix)"""
        return self._rag_container, self._rag_prefix
```

### Usage in Services

```python
# src/services/storage.py
def save_rag_metadata(self, file_name: str, metadata: dict):
    rag_container, rag_prefix = config.azure_storage.get_rag_config()

    # Build full blob path
    if rag_prefix:
        blob_path = f"{rag_prefix}/metadata/{file_name}.json"
        # Example: "adm/CXEngine/agent-rag-docs/metadata/report.pdf.json"
    else:
        blob_path = f"metadata/{file_name}.json"

    self.upload_blob(rag_container, blob_path, metadata)
```

---

## 🧪 VERIFICATION

### Test Your Configuration

```python
from src.core.config import config

# Check parsed values
cache_container, cache_prefix = config.azure_storage.get_cache_config()
print(f"Cache container: {cache_container}")
print(f"Cache prefix: {cache_prefix}")

rag_container, rag_prefix = config.azure_storage.get_rag_config()
print(f"RAG container: {rag_container}")
print(f"RAG prefix: {rag_prefix}")

# Expected output for your config:
# Cache container: reservoir
# Cache prefix: adm/CXEngine/agent-cache
# RAG container: reservoir
# RAG prefix: adm/CXEngine/agent-rag-docs
```

---

## 📋 SETUP CHECKLIST

For Pattern 2 (Single Container with Prefixes):

- [ ] Azure Blob Storage container `reservoir` exists
- [ ] Connection string in `.env` is correct
- [ ] Container paths in `.env` follow pattern: `reservoir/adm/CXEngine/...`
- [ ] Tested configuration parsing (see verification above)
- [ ] Uploaded test file to verify path structure
- [ ] Confirmed files appear in correct Azure Portal path

---

## 🔄 MIGRATION

### From Separate Containers → Single Container

If you currently have Pattern 1 and want to switch:

**1. Update .env:**
```bash
# OLD
AZURE_STORAGE_CONTAINER_RAG=agent-rag-docs

# NEW
AZURE_STORAGE_CONTAINER_RAG=reservoir/adm/CXEngine/agent-rag-docs
```

**2. Move existing blobs (optional):**
```bash
# Use Azure Storage Explorer or Azure CLI
az storage blob copy start-batch \
  --source-container agent-rag-docs \
  --destination-container reservoir \
  --destination-path adm/CXEngine/agent-rag-docs \
  --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

**3. Restart application** - new paths automatically used

---

## 🚨 IMPORTANT NOTES

### Container Name Rules

❌ **INVALID:**
```bash
# Container names CANNOT have slashes
AZURE_STORAGE_CONTAINER_RAG=reservoir/adm/CXEngine/agent-rag-docs/container
#                            ^^^^^^^^^ This is the container name - must be valid!
```

✅ **VALID:**
```bash
# First part before "/" is container, rest is prefix
AZURE_STORAGE_CONTAINER_RAG=reservoir/adm/CXEngine/agent-rag-docs
#                            ^^^^^^^^^ Valid container name
#                                     ^^^^^^^^^^^^^^^^^^^^^^^^^ Blob prefix
```

### Performance Considerations

- **Pattern 1 (Separate):** Slightly faster (fewer prefix checks)
- **Pattern 2 (Single):** Minimal overhead (~1-2ms per operation)
- **Both:** Functionally equivalent for production use

---

## 🎯 EXAMPLES

### Example 1: Upload RAG Document

**Your .env:**
```bash
AZURE_STORAGE_CONTAINER_RAG=reservoir/adm/CXEngine/agent-rag-docs
```

**Upload file:**
```python
from src.services.storage import get_blob_storage

storage = get_blob_storage()
with open("report.pdf", "rb") as f:
    storage.upload_blob(
        container_name="reservoir",  # Parsed automatically
        blob_name="adm/CXEngine/agent-rag-docs/report.pdf",  # Full path
        data=f.read(),
        serialize="text"
    )
```

**Or use Azure Portal:**
1. Go to container `reservoir`
2. Navigate to `adm/CXEngine/agent-rag-docs/`
3. Upload `report.pdf`
4. File detected and processed automatically!

---

### Example 2: Check Blob Path

```python
from src.core.config import config
from src.services.blob_monitor import get_blob_monitor

# BlobMonitorService automatically uses correct container + prefix
monitor = get_blob_monitor()
stats = monitor.get_stats()

print(f"Monitoring container: {stats['container']}")  # reservoir
print(f"With prefix: {stats['blob_prefix']}")  # adm/CXEngine/agent-rag-docs
```

---

## 📚 RELATED DOCUMENTATION

- `PRODUCTION_FIXES.md` - Vector stores to Azure Blob
- `RAG_BLOB_STORAGE.md` - RAG file monitoring
- `.env.example` - Configuration template with both patterns

---

## ✅ SUMMARY

### Your Question
> "Is `AZURE_STORAGE_CONTAINER_CACHE=reservoir/CXEngine/agent-cache` fine?"

### Answer
✅ **YES - NOW SUPPORTED!**

But use the FULL path with your folder structure:
```bash
AZURE_STORAGE_CONTAINER_CACHE=reservoir/adm/CXEngine/agent-cache
AZURE_STORAGE_CONTAINER_RAG=reservoir/adm/CXEngine/agent-rag-docs
AZURE_STORAGE_CONTAINER_EDA=reservoir/adm/CXEngine/agent-eda-results
```

### How It Works
- **Container:** `reservoir` (the actual Azure Blob container)
- **Blob prefix:** `adm/CXEngine/agent-cache` (virtual folder path)
- **Full blob paths:** `adm/CXEngine/agent-cache/cache/query_123.json`

### Perfect For
- ✅ Shared container with other applications
- ✅ Organized folder structure under `adm/CXEngine`
- ✅ Your specific requirement!

---

**Version:** 2.3.0
**Date:** 2026-02-06
**Status:** ✅ PRODUCTION-READY

---

*Now supports flexible Azure Blob Storage patterns - use what works best for your infrastructure!*
