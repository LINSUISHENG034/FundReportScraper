# Phase 6 Guidance: E2E Parsing Verification

## 1. Objective

To implement a comprehensive end-to-end (E2E) test that verifies the entire backend workflow, from triggering a download to the successful parsing of the report data. This will close the testing gap identified after Phase 5 and ensure the entire data processing pipeline is robust and correct.

This plan involves two main parts:
1.  Creating a new API endpoint to query the status of Celery tasks.
2.  Creating a new E2E test script that uses this endpoint to verify the full download-and-parse chain.

## 2. Part 1: Implement the Task Status API

To test an asynchronous workflow, we need a way to check on its progress. We will create a dedicated API endpoint for this purpose.

### Action 1.1: Create the Task Router File

Create a new file `src/api/routes/tasks.py`. This file will contain the logic for querying Celery task results.

**Path**: `src/api/routes/tasks.py`
**Content**:
```python
"""
API Route for querying the status of Celery tasks.
"""
from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from src.core.celery_app import app as celery_app
from src.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.get("/tasks/{task_id}/status", tags=["Tasks Status"])
def get_task_status(task_id: str):
    """
    Query the status and result of a Celery task.
    
    This endpoint allows polling for the result of a long-running asynchronous task.
    """
    bound_logger = logger.bind(task_id=task_id)
    bound_logger.info("task.status.requested")

    try:
        # Use the task_id to get the AsyncResult object from Celery
        task_result = AsyncResult(id=task_id, app=celery_app)

        response_data = {
            "task_id": task_id,
            "status": task_result.status,
            "ready": task_result.ready(),
        }

        if task_result.successful():
            bound_logger.info("task.status.success")
            # .get() retrieves the final return value of the task
            response_data["result"] = task_result.get()
        elif task_result.failed():
            bound_logger.error("task.status.failed", reason=str(task_result.info))
            response_data["error_info"] = str(task_result.info)
            # For security, we might not want to expose the full traceback in production
            # response_data["traceback"] = task_result.traceback
        else:
            # Task is still pending, revoked, or in another state
            bound_logger.info("task.status.pending_or_other")
            response_data["result"] = None

        return response_data

    except Exception as e:
        bound_logger.error("task.status.api_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while fetching task status: {e}")

```

### Action 1.2: Register the New Router

Now, we must tell the main FastAPI application to use this new router.

**File to Modify**: `src/main.py`
**Action**: Import the new `tasks` router and include it in the app.

```python
# In src/main.py

# --- SEARCH ---
# 导入路由模块
from src.api.routes import reports, downloads

app.include_router(reports.router, tags=["报告搜索"])
app.include_router(downloads.router, tags=["下载任务"])

# --- REPLACE WITH ---
# 导入路由模块
from src.api.routes import reports, downloads, tasks

app.include_router(reports.router, tags=["报告搜索"])
app.include_router(downloads.router, tags=["下载任务"])
app.include_router(tasks.router, tags=["任务状态"])
```

## 3. Part 2: Refactor Celery & Implement E2E Parsing Test

### Action 2.1: Refactor Task Orchestration

A small but critical change is needed in `src/tasks/download_tasks.py`. The `start_download_pipeline` task must return the ID of the `chord` it creates, so the client can track the final result.

**File to Modify**: `src/tasks/download_tasks.py`
**Action**: Modify `start_download_pipeline` to capture and return the chord's task ID.

```python
# In src/tasks/download_tasks.py

# --- SEARCH ---
@celery_app.task(bind=True)
def start_download_pipeline(
    self, task_id: str, reports_to_process: List[Dict[str, Any]], save_dir: str
):
    # ... (existing code) ...
    callback = finalize_batch_download.s(task_id=task_id)
    chord(job_group)(callback)

    bound_logger.info(
        "start_download_pipeline.pipeline_started", report_count=len(reports_to_process)
    )

# --- REPLACE WITH ---
@celery_app.task(bind=True)
def start_download_pipeline(
    self, task_id: str, reports_to_process: List[Dict[str, Any]], save_dir: str
):
    # ... (existing code up to the chord) ...
    callback = finalize_batch_download.s(task_id=task_id)
    
    # Capture the AsyncResult of the chord
    chord_result = chord(job_group)(callback)

    bound_logger.info(
        "start_download_pipeline.pipeline_started", 
        report_count=len(reports_to_process),
        chord_task_id=chord_result.id # Log the chord's ID
    )
    
    # Return the chord's ID so the client can poll it for the final result
    return {"main_task_id": task_id, "chord_task_id": chord_result.id}
```
*Note*: The `/api/downloads` endpoint in `src/api/routes/downloads.py` will now automatically return this new dictionary.

### Action 2.2: Create the E2E Parsing Test Script

This new script will test the full chain.

**Path**: `scripts/verification/verify_e2e_parsing.py`
**Content**:
```python
"""
E2E Verification Script for the Full Download-and-Parse Workflow
"""
import httpx
import logging
import time
from pathlib import Path
from typing import List, Dict, Any

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"
DOWNLOAD_DIR = Path("data/downloads/e2e_parsing_verification")
VERIFICATION_TIMEOUT_SECONDS = 90  # Increased timeout for the full chain
POLL_INTERVAL_SECONDS = 5

# --- Test Target ---
TARGET_YEAR = 2024
TARGET_REPORT_TYPE = "FB010010"
TARGET_FUND_CODE = "015975"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def search_for_reports(client: httpx.Client) -> List[Dict[str, Any]]:
    logging.info("STEP 1: Searching for reports...")
    params = {"year": TARGET_YEAR, "report_type": TARGET_REPORT_TYPE, "fund_code": TARGET_FUND_CODE}
    response = client.get(f"{API_BASE_URL}/api/reports", params=params)
    response.raise_for_status()
    data = response.json()
    reports = data["data"]
    logging.info(f"SUCCESS: Found {len(reports)} report(s).")
    return reports

def trigger_download_and_parse(client: httpx.Client, reports: List[Dict[str, Any]]) -> str:
    logging.info("STEP 2: Triggering download and parse pipeline...")
    payload = {"reports": reports, "save_dir": str(DOWNLOAD_DIR)}
    response = client.post(f"{API_BASE_URL}/api/downloads", json=payload)
    response.raise_for_status()
    data = response.json()
    
    # The endpoint now returns the ID of the chord's callback task
    chord_task_id = data["chord_task_id"]
    logging.info(f"SUCCESS: Pipeline task created. Polling Chord Task ID: {chord_task_id}")
    return chord_task_id

def verify_parsing_result(client: httpx.Client, task_id: str, expected_success_count: int) -> bool:
    logging.info(f"STEP 3: Polling task status for Task ID: {task_id}...")
    start_time = time.time()
    while time.time() - start_time < VERIFICATION_TIMEOUT_SECONDS:
        try:
            response = client.get(f"{API_BASE_URL}/api/tasks/{task_id}/status")
            if response.status_code == 200:
                data = response.json()
                logging.info(f"  - Polling... current status: {data['status']}")
                if data["ready"]:
                    if data["status"] == "SUCCESS":
                        final_result = data["result"]
                        logging.info(f"SUCCESS: Task completed. Final result: {final_result}")
                        # Verification logic
                        if final_result.get("successful") == expected_success_count:
                            logging.info(f"✅ Verification PASSED: Successful count ({final_result.get('successful')}) matches expected count ({expected_success_count}).")
                            return True
                        else:
                            logging.error(f"❌ Verification FAILED: Successful count ({final_result.get('successful')}) does not match expected count ({expected_success_count}).")
                            return False
                    else: # FAILURE
                        logging.error(f"❌ Verification FAILED: Task reported status {data['status']}. Error: {data.get('error_info')}")
                        return False
            else:
                logging.warning(f"  - Polling... received status code {response.status_code}")

        except Exception as e:
            logging.error(f"  - Polling... an error occurred: {e}")
        
        time.sleep(POLL_INTERVAL_SECONDS)

    logging.error(f"❌ Verification FAILED: Timed out after {VERIFICATION_TIMEOUT_SECONDS} seconds.")
    return False

def main():
    logging.info("--- Starting E2E Parsing Verification Script ---")
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        reports = search_for_reports(client)
        if not reports:
            logging.error("Test failed at Step 1.")
            return

        chord_task_id = trigger_download_and_parse(client, reports)
        if not chord_task_id:
            logging.error("Test failed at Step 2.")
            return

        success = verify_parsing_result(client, chord_task_id, len(reports))
        if success:
            logging.info("✅ ✅ ✅ E2E PARSING VERIFICATION SUCCEEDED! ✅ ✅ ✅")
        else:
            logging.error("❌ ❌ ❌ E2E PARSING VERIFICATION FAILED! ❌ ❌ ❌")

if __name__ == "__main__":
    main()
```

## 4. Verification Steps

1.  Ensure the development team implements all actions described in Part 1 and Part 2.
2.  Start the backend application (`uvicorn`) and the Celery worker (`celery`).
3.  Run the new verification script from the project root:
    ```bash
    python scripts/verification/verify_e2e_parsing.py
    ```
4.  Observe the output. The script should report `✅ ✅ ✅ E2E PARSING VERIFICATION SUCCEEDED! ✅ ✅ ✅`.

This concludes the plan for implementing full E2E verification.
