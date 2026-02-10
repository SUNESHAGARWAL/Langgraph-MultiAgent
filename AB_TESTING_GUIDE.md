# A/B Testing & Model Versioning Guide
## Multi-Agent Orchestrator v3.0.0+

**Date:** 2026-02-10
**Feature:** Model Versioning + A/B Testing + Feature Flags
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Model Versioning](#model-versioning)
5. [A/B Testing](#ab-testing)
6. [Feature Flags](#feature-flags)
7. [Usage Examples](#usage-examples)
8. [Analyzing Results](#analyzing-results)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### What is A/B Testing?

A/B testing allows you to:
- **Compare different agent strategies** (e.g., with vs without grader)
- **Test new prompts** or routing logic
- **Measure impact** on success rate, latency, cost
- **Gradual rollout** of new features (10% → 25% → 50% → 100%)
- **Risk-free experimentation** with automatic traffic splitting

### Key Features

✅ **Model Versioning** - Register and manage multiple agent versions
✅ **Traffic Splitting** - Deterministic user assignment (same user always gets same version)
✅ **Feature Flags** - Toggle features per user or percentage
✅ **Experiment Tracking** - Automatic metrics tracking per version
✅ **Canary Deployment** - Gradual rollout with monitoring
✅ **Persistent Configuration** - JSON-based config survives restarts

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                  VERSION MANAGER                             │
│  - Registers versions (3.0.0, 3.1.0, 3.2.0)                 │
│  - Assigns users to versions (deterministic hashing)        │
│  - Manages experiments and traffic splits                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ↓            ↓            ↓
    ┌────────┐  ┌────────┐  ┌────────┐
    │ v3.0.0 │  │ v3.1.0 │  │ v3.2.0 │
    │  70%   │  │  20%   │  │  10%   │
    └────────┘  └────────┘  └────────┘

┌─────────────────────────────────────────────────────────────┐
│                  FEATURE FLAGS                               │
│  - use_grader: 100%                                         │
│  - parallel_execution: 100%                                 │
│  - enhanced_prompts: 10% (testing)                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  METRICS TRACKER                             │
│  - Tracks per-version metrics                               │
│  - model_version, experiment_id in QueryMetrics            │
│  - Compare success rate, latency, cost by version          │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
config/
├── versions.json          # Version registry and experiments
└── feature_flags.json     # Feature flag configuration

data/
└── faiss_rag_index/       # Persistent FAISS index
    ├── index.faiss        # Vector index
    └── index.pkl          # Metadata

src/
└── versioning.py          # VersionManager + FeatureFlags
```

---

## Quick Start

### 1. Initialize Versioning System

```python
from src.versioning import get_version_manager, get_feature_flags

# Get singletons
version_manager = get_version_manager()
feature_flags = get_feature_flags()

# System will auto-create:
# - config/versions.json
# - config/feature_flags.json
```

**Default Configuration:**
- **v3.0.0** (Production): 100% rollout
- **v3.1.0** (Experimental): 0% rollout, disabled
- **v3.2.0** (Experimental): 0% rollout, disabled

### 2. Query with Version Assignment

```python
from src.agent_enhanced import get_agent
from src.versioning import get_version_manager
from src.utils.metrics import get_metrics_tracker
from langchain_core.messages import HumanMessage
import uuid

# Initialize
agent = get_agent()
version_manager = get_version_manager()
metrics_tracker = get_metrics_tracker()

# User makes a query
user_id = "user-12345"
question = "What were our top 5 products by revenue?"

# Get version for this user
model_version = version_manager.get_version_for_user(user_id)

# Start tracking with version
query_id = str(uuid.uuid4())
metrics = metrics_tracker.start_query(
    query_id=query_id,
    question=question,
    thread_id=user_id,
    model_version=model_version  # Track which version
)

# Execute query
result = agent.invoke({
    "messages": [HumanMessage(content=question)],
    "query_id": query_id,
    "iterations": 0,
    "final_answer": ""
}, config={"configurable": {"thread_id": user_id}})

# End tracking
metrics_tracker.end_query(query_id, success=True, iterations=result["iterations"])

print(f"User {user_id} got version {model_version}")
print(f"Answer: {result['final_answer']}")
```

---

## Model Versioning

### Register a New Version

```python
from src.versioning import get_version_manager

version_manager = get_version_manager()

# Register v3.1.0 - enhanced supervisor prompts
version_manager.register_version(
    version="3.1.0",
    name="Enhanced Supervisor v1",
    description="Improved supervisor prompts with better routing logic",
    rollout_percentage=0.0,  # Start at 0%
    enabled=False,           # Not active yet
    features={
        "use_grader": True,
        "parallel_execution": True,
        "semantic_cache": True,
        "enhanced_prompts": True,  # New feature
    }
)

print("✓ Registered v3.1.0")
```

**Configuration Saved To:** `config/versions.json`

```json
{
  "versions": [
    {
      "version": "3.0.0",
      "name": "Production Stable",
      "rollout_percentage": 1.0,
      "enabled": true,
      "features": {
        "use_grader": true,
        "parallel_execution": true,
        "semantic_cache": true
      }
    },
    {
      "version": "3.1.0",
      "name": "Enhanced Supervisor v1",
      "rollout_percentage": 0.0,
      "enabled": false,
      "features": {
        "use_grader": true,
        "parallel_execution": true,
        "semantic_cache": true,
        "enhanced_prompts": true
      }
    }
  ]
}
```

### Canary Deployment (Gradual Rollout)

```python
from src.versioning import get_version_manager
import time

version_manager = get_version_manager()

# Step 1: Enable v3.1.0 for 10% of users
version_manager.update_rollout("3.1.0", 0.10)
print("✓ Rolled out v3.1.0 to 10% of users")

# Monitor metrics for 1 hour...
time.sleep(3600)

# Check metrics (see Analyzing Results section)
# If metrics look good, continue rollout

# Step 2: Increase to 25%
version_manager.update_rollout("3.1.0", 0.25)
print("✓ Rolled out v3.1.0 to 25% of users")

# Monitor for another hour...
time.sleep(3600)

# Step 3: Increase to 50%
version_manager.update_rollout("3.1.0", 0.50)
print("✓ Rolled out v3.1.0 to 50% of users")

# Monitor...
time.sleep(3600)

# Step 4: Full rollout to 100%
version_manager.update_rollout("3.1.0", 1.00)
print("✓ Rolled out v3.1.0 to 100% of users")

# Step 5: Disable old version
version_manager.update_rollout("3.0.0", 0.0)
print("✓ Sunset v3.0.0")
```

**User Assignment is Deterministic:**
- Same user_id always gets same version (based on MD5 hash)
- User "alice" gets v3.0.0 → will always get v3.0.0 (until rollout changes)
- User "bob" gets v3.1.0 → will always get v3.1.0

---

## A/B Testing

### Create an Experiment

```python
from src.versioning import get_version_manager

version_manager = get_version_manager()

# Experiment: Compare standard grading vs strict grading
experiment = version_manager.create_experiment(
    experiment_id="grading_test_001",
    name="Standard vs Strict Grading",
    description="Compare grading strategies to measure impact on quality",
    control_version="3.0.0",      # Baseline (standard grading)
    treatment_versions=["3.2.0"],  # Test version (strict grading)
    traffic_split={
        "3.0.0": 0.70,  # 70% get control
        "3.2.0": 0.30   # 30% get treatment
    }
)

print(f"✓ Created experiment: {experiment.experiment_id}")
print(f"  Control: {experiment.control_version} (70%)")
print(f"  Treatment: {experiment.treatment_versions} (30%)")
```

**Saved To:** `config/versions.json`

```json
{
  "experiments": [
    {
      "experiment_id": "grading_test_001",
      "name": "Standard vs Strict Grading",
      "control_version": "3.0.0",
      "treatment_versions": ["3.2.0"],
      "traffic_split": {
        "3.0.0": 0.70,
        "3.2.0": 0.30
      },
      "active": true,
      "start_date": "2026-02-10T10:00:00",
      "success_metrics": [
        "avg_latency",
        "success_rate",
        "validation_pass_rate",
        "user_satisfaction"
      ]
    }
  ]
}
```

### Query with Experiment

```python
from src.agent_enhanced import get_agent
from src.versioning import get_version_manager
from src.utils.metrics import get_metrics_tracker

agent = get_agent()
version_manager = get_version_manager()
metrics_tracker = get_metrics_tracker()

user_id = "user-789"
question = "What is our customer churn rate?"

# Get version for user in experiment
model_version = version_manager.get_version_for_user(
    user_id=user_id,
    experiment_id="grading_test_001"  # Participate in experiment
)

# Start tracking with experiment
query_id = str(uuid.uuid4())
metrics = metrics_tracker.start_query(
    query_id=query_id,
    question=question,
    thread_id=user_id,
    model_version=model_version,
    experiment_id="grading_test_001"  # Track experiment
)

# Execute query
result = agent.invoke(...)

print(f"User {user_id} assigned to version {model_version}")
# User gets deterministically assigned to either v3.0.0 or v3.2.0
```

### Multi-Variant Testing (A/B/C)

```python
# Test 3 versions simultaneously
experiment = version_manager.create_experiment(
    experiment_id="routing_test_002",
    name="Routing Strategy Comparison",
    description="Compare 3 different routing strategies",
    control_version="3.0.0",
    treatment_versions=["3.1.0", "3.3.0"],
    traffic_split={
        "3.0.0": 0.34,  # 34% - Standard routing
        "3.1.0": 0.33,  # 33% - Enhanced prompts
        "3.3.0": 0.33   # 33% - Fast mode (no grader)
    }
)
```

---

## Feature Flags

### Enable/Disable Features

```python
from src.versioning import get_feature_flags

feature_flags = get_feature_flags()

# Check if feature is enabled
user_id = "user-123"

if feature_flags.is_enabled("use_grader", user_id):
    print("✓ Grader validation is enabled for this user")
    # Use grader
else:
    print("✗ Grader validation is disabled for this user")
    # Skip grader (faster but lower quality)
```

### Gradual Feature Rollout

```python
# Roll out "enhanced_prompts" feature to 10% of users
feature_flags.set_flag(
    flag_name="enhanced_prompts",
    enabled=True,
    rollout_percentage=0.10  # 10% of users
)

# Same user always gets same result (deterministic)
if feature_flags.is_enabled("enhanced_prompts", "user-alice"):
    # Use enhanced prompts
    ...
```

### Use in Agent Code

```python
from src.versioning import get_feature_flags

feature_flags = get_feature_flags()

def supervisor_node(state: AgentState):
    user_id = state.get("thread_id")

    # Check feature flag
    if feature_flags.is_enabled("enhanced_prompts", user_id):
        system_prompt = ENHANCED_SUPERVISOR_PROMPT
    else:
        system_prompt = STANDARD_SUPERVISOR_PROMPT

    # Continue with supervisor logic...
    response = model.invoke([SystemMessage(content=system_prompt), ...])
    return {"next_agent": response.content}
```

### Available Feature Flags

**Default Flags in `config/feature_flags.json`:**

```json
{
  "use_grader": {
    "enabled": true,
    "rollout_percentage": 1.0,
    "description": "Enable result grader validation"
  },
  "parallel_execution": {
    "enabled": true,
    "rollout_percentage": 1.0,
    "description": "Enable parallel agent execution"
  },
  "semantic_cache": {
    "enabled": true,
    "rollout_percentage": 1.0,
    "description": "Enable semantic caching for Genie"
  },
  "enhanced_prompts": {
    "enabled": false,
    "rollout_percentage": 0.0,
    "description": "Use enhanced supervisor prompts"
  },
  "strict_grading": {
    "enabled": false,
    "rollout_percentage": 0.0,
    "description": "Use strict grading criteria"
  },
  "fast_mode": {
    "enabled": false,
    "rollout_percentage": 0.0,
    "description": "Skip grader for faster responses"
  }
}
```

---

## Usage Examples

### Example 1: Simple Version Assignment

```python
from src.versioning import get_version_manager

version_manager = get_version_manager()

# Different users get assigned to versions based on rollout
users = ["alice", "bob", "charlie", "diana", "eve"]

for user in users:
    version = version_manager.get_version_for_user(user)
    print(f"{user} → {version}")

# Output (with 70% on v3.0.0, 30% on v3.1.0):
# alice → 3.0.0
# bob → 3.1.0
# charlie → 3.0.0
# diana → 3.0.0
# eve → 3.0.0
```

### Example 2: Experiment Participation

```python
# Create experiment
version_manager.create_experiment(
    experiment_id="exp_001",
    name="Test New Features",
    control_version="3.0.0",
    treatment_versions=["3.1.0"],
    traffic_split={"3.0.0": 0.5, "3.1.0": 0.5}  # 50/50 split
)

# Users participate
for user in ["alice", "bob", "charlie", "diana"]:
    version = version_manager.get_version_for_user(user, experiment_id="exp_001")
    print(f"{user} → {version}")

# Output (50/50 split):
# alice → 3.0.0
# bob → 3.1.0
# charlie → 3.1.0
# diana → 3.0.0
```

### Example 3: Feature Flag Testing

```python
# Enable "fast_mode" for 20% of users
feature_flags.set_flag("fast_mode", enabled=True, rollout_percentage=0.20)

# Check for 100 users
fast_mode_count = 0

for i in range(100):
    user_id = f"user-{i}"
    if feature_flags.is_enabled("fast_mode", user_id):
        fast_mode_count += 1

print(f"{fast_mode_count}/100 users have fast_mode enabled")
# Output: ~20/100 users have fast_mode enabled
```

### Example 4: API Integration

```python
# In src/api.py - FastAPI endpoint

from fastapi import FastAPI
from src.versioning import get_version_manager, get_feature_flags

app = FastAPI()
version_manager = get_version_manager()
feature_flags = get_feature_flags()

@app.post("/api/v1/query")
async def execute_query(request: QueryRequest):
    user_id = request.thread_id or str(uuid.uuid4())

    # Get version for user
    model_version = version_manager.get_version_for_user(user_id)

    # Check feature flags
    use_grader = feature_flags.is_enabled("use_grader", user_id)

    # Start metrics tracking
    query_id = str(uuid.uuid4())
    metrics = metrics_tracker.start_query(
        query_id=query_id,
        question=request.question,
        thread_id=user_id,
        model_version=model_version
    )

    # Execute with version-specific logic
    # ...

    return {
        "query_id": query_id,
        "model_version": model_version,
        "answer": result["final_answer"],
        "used_grader": use_grader
    }
```

---

## Analyzing Results

### Compare Version Metrics

```python
from src.utils.metrics import get_metrics_tracker

metrics_tracker = get_metrics_tracker()

# Get all metrics
all_metrics = metrics_tracker.get_all_metrics()

# Group by version
from collections import defaultdict

version_stats = defaultdict(list)

for query_id, metrics in all_metrics.items():
    version = metrics.model_version
    version_stats[version].append({
        "duration": metrics.duration(),
        "cost": metrics.estimated_cost(),
        "success": metrics.success,
        "iterations": metrics.iterations,
        "cache_hit_rate": metrics.cache_hit_rate()
    })

# Calculate averages per version
for version, stats in version_stats.items():
    avg_duration = sum(s["duration"] for s in stats) / len(stats)
    avg_cost = sum(s["cost"] for s in stats) / len(stats)
    success_rate = sum(s["success"] for s in stats) / len(stats)
    avg_iterations = sum(s["iterations"] for s in stats) / len(stats)

    print(f"\nVersion {version} ({len(stats)} queries):")
    print(f"  Avg Duration: {avg_duration:.2f}s")
    print(f"  Avg Cost: ${avg_cost:.4f}")
    print(f"  Success Rate: {success_rate*100:.1f}%")
    print(f"  Avg Iterations: {avg_iterations:.1f}")
```

**Example Output:**

```
Version 3.0.0 (700 queries):
  Avg Duration: 8.5s
  Avg Cost: $0.0234
  Success Rate: 92.0%
  Avg Iterations: 1.8

Version 3.1.0 (300 queries):
  Avg Duration: 7.2s
  Avg Cost: $0.0198
  Success Rate: 95.0%
  Avg Iterations: 1.5

Analysis: v3.1.0 is 15% faster, 15% cheaper, and 3% more successful!
```

### Export to MLflow

```python
import mlflow

# Log experiment results to MLflow
for version, stats in version_stats.items():
    with mlflow.start_run(run_name=f"version_{version}"):
        mlflow.log_param("model_version", version)
        mlflow.log_metric("avg_duration", avg_duration)
        mlflow.log_metric("avg_cost", avg_cost)
        mlflow.log_metric("success_rate", success_rate)
        mlflow.log_metric("avg_iterations", avg_iterations)
```

### Decision Framework

**When to promote a version:**

✅ **Success rate** improved by ≥2%
✅ **Latency** reduced by ≥10% OR < 10s P99
✅ **Cost** reduced by ≥10% OR increased <5%
✅ **No increase in errors**

**When to rollback:**

❌ Success rate drops >2%
❌ Latency increases >20%
❌ Error rate >5%
❌ User complaints

---

## Best Practices

### 1. Start Small, Scale Gradually

```python
# ✅ GOOD: Gradual rollout
version_manager.update_rollout("3.1.0", 0.10)  # 10%
# ... monitor for 1 hour ...
version_manager.update_rollout("3.1.0", 0.25)  # 25%
# ... monitor for 1 hour ...
version_manager.update_rollout("3.1.0", 1.00)  # 100%

# ❌ BAD: Immediate 100% rollout
version_manager.update_rollout("3.1.0", 1.00)  # Risky!
```

### 2. Always Have a Control Group

```python
# ✅ GOOD: 70/30 split
experiment = version_manager.create_experiment(
    traffic_split={"3.0.0": 0.70, "3.1.0": 0.30}
)

# ❌ BAD: 100% on new version (no baseline)
experiment = version_manager.create_experiment(
    traffic_split={"3.1.0": 1.00}
)
```

### 3. Track Everything

```python
# ✅ GOOD: Track version and experiment
metrics_tracker.start_query(
    query_id=query_id,
    question=question,
    thread_id=user_id,
    model_version=model_version,     # Track version
    experiment_id=experiment_id      # Track experiment
)
```

### 4. Use Feature Flags for New Features

```python
# ✅ GOOD: Feature flag allows quick disable
if feature_flags.is_enabled("new_feature", user_id):
    # Use new feature
else:
    # Use stable fallback

# Can disable instantly if issues arise:
# feature_flags.set_flag("new_feature", enabled=False)
```

### 5. Document Experiments

```python
# ✅ GOOD: Clear description
experiment = version_manager.create_experiment(
    experiment_id="grading_test_001",
    name="Standard vs Strict Grading",
    description="Test strict grading to see if it improves quality by 5% without increasing latency >10%",
    # ...
)
```

### 6. Set Success Criteria Before Testing

```
Before running experiment:
1. Define hypothesis: "Strict grading will improve quality by 5%"
2. Define success metrics: validation_pass_rate, avg_latency, cost
3. Define acceptance criteria: +5% quality, <10% latency increase
4. Define sample size: 1000 queries per version
5. Define duration: 7 days
```

---

## Troubleshooting

### Issue: User keeps getting different versions

**Problem:** User assignment not deterministic

**Solution:** Ensure you pass same `user_id` consistently

```python
# ❌ BAD: Different IDs
version_manager.get_version_for_user(str(uuid.uuid4()))  # Random each time

# ✅ GOOD: Same ID
user_id = request.user_id or request.session_id
version_manager.get_version_for_user(user_id)
```

### Issue: Rollout percentage not working

**Problem:** Config not reloaded after changes

**Solution:** Restart application or reload config

```python
# Reload config
version_manager._load_config()
```

### Issue: Feature flag always returns same value

**Problem:** Not passing user_id

```python
# ❌ BAD: No user_id (checks global only)
feature_flags.is_enabled("new_feature")  # Always same result

# ✅ GOOD: Pass user_id for % rollout
feature_flags.is_enabled("new_feature", user_id)
```

### Issue: Cannot find config files

**Problem:** Config directory doesn't exist

**Solution:** System auto-creates, but can manually create:

```bash
mkdir -p config
python -c "from src.versioning import get_version_manager; get_version_manager()"
```

---

## Summary

### Key Commands

```python
# Initialize
from src.versioning import get_version_manager, get_feature_flags
version_manager = get_version_manager()
feature_flags = get_feature_flags()

# Register version
version_manager.register_version("3.1.0", "New Version", "Description")

# Gradual rollout
version_manager.update_rollout("3.1.0", 0.10)  # 10%
version_manager.update_rollout("3.1.0", 0.50)  # 50%
version_manager.update_rollout("3.1.0", 1.00)  # 100%

# Create A/B test
version_manager.create_experiment(
    experiment_id="exp_001",
    name="Test Name",
    control_version="3.0.0",
    treatment_versions=["3.1.0"],
    traffic_split={"3.0.0": 0.7, "3.1.0": 0.3}
)

# Get user's version
version = version_manager.get_version_for_user(user_id)
version = version_manager.get_version_for_user(user_id, experiment_id="exp_001")

# Feature flags
feature_flags.set_flag("new_feature", enabled=True, rollout_percentage=0.2)
is_enabled = feature_flags.is_enabled("new_feature", user_id)

# Track metrics
metrics_tracker.start_query(
    query_id, question, user_id,
    model_version=version,
    experiment_id=experiment_id
)
```

### Configuration Files

- **`config/versions.json`** - Version registry and experiments
- **`config/feature_flags.json`** - Feature flag settings
- **`data/faiss_rag_index/`** - Persistent FAISS index (auto-saved)

### Next Steps

1. ✅ FAISS is now persistent (loads from disk after first run)
2. ✅ Model versioning system ready to use
3. ✅ A/B testing framework operational
4. ✅ Feature flags available
5. ⏭️ Start experimenting with your own versions!

---

**Version:** 3.0.0+
**Date:** 2026-02-10
**Status:** ✅ Ready for Production A/B Testing
