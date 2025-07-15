"""
E2E Verification Script for the Full Download-and-Parse Workflow (Corrected)
"""
import httpx
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"
DOWNLOAD_DIR = Path("data/downloads/e2e_final_verification")
VERIFICATION_TIMEOUT_SECONDS = 90
POLL_INTERVAL_SECONDS = 5

# --- Test Target ---
TARGET_YEAR = 2024
TARGET_REPORT_TYPE = "FB010010"
TARGET_FUND_CODE = "015975"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def search_for_reports(client: httpx.Client) -> List[Dict[str, Any]]:
    """STEP 1: Find reports to process."""
    logging.info("STEP 1: Searching for reports...")
    params = {"year": TARGET_YEAR, "report_type": TARGET_REPORT_TYPE, "fund_code": TARGET_FUND_CODE}
    response = client.get(f"{API_BASE_URL}/api/reports", params=params)
    response.raise_for_status()
    reports = response.json()["data"]
    logging.info(f"SUCCESS: Found {len(reports)} report(s).")
    return reports

def trigger_pipeline(client: httpx.Client, reports: List[Dict[str, Any]]) -> Optional[str]:
    """STEP 2: Trigger the pipeline and get the orchestrator task ID."""
    logging.info("STEP 2: Triggering download and parse pipeline...")
    payload = {"reports": reports, "save_dir": str(DOWNLOAD_DIR)}
    response = client.post(f"{API_BASE_URL}/api/downloads", json=payload)
    response.raise_for_status()
    orchestrator_task_id = response.json().get("task_id")
    if not orchestrator_task_id:
        logging.error("API response did not contain 'task_id'.")
        return None
    logging.info(f"SUCCESS: Pipeline triggered. Orchestrator Task ID: {orchestrator_task_id}")
    return orchestrator_task_id

def get_chord_task_id(client: httpx.Client, orchestrator_task_id: str) -> Optional[str]:
    """STEP 3: Poll the orchestrator task to get the final chord task ID."""
    logging.info(f"STEP 3: Polling orchestrator task ({orchestrator_task_id}) to get chord ID...")
    start_time = time.time()
    while time.time() - start_time < 30: # Short timeout for this simple task
        response = client.get(f"{API_BASE_URL}/api/tasks/{orchestrator_task_id}/status")
        response.raise_for_status()
        data = response.json()
        if data["ready"]:
            if data["status"] == "SUCCESS":
                chord_id = data.get("result", {}).get("chord_task_id")
                if chord_id:
                    logging.info(f"SUCCESS: Got Chord Task ID: {chord_id}")
                    return chord_id
                else:
                    logging.error(f"Orchestrator task succeeded but did not return a 'chord_task_id'. Result: {data.get('result')}")
                    return None
            else: # FAILURE
                logging.error(f"Orchestrator task failed. Info: {data.get('error_info')}")
                return None
        time.sleep(2)
    logging.error("Timeout waiting for orchestrator task to complete.")
    return None

def verify_final_result(client: httpx.Client, chord_task_id: str, expected_count: int) -> bool:
    """STEP 4: Poll the chord task for the final result."""
    logging.info(f"STEP 4: Polling chord task ({chord_task_id}) for final result...")
    start_time = time.time()
    while time.time() - start_time < VERIFICATION_TIMEOUT_SECONDS:
        response = client.get(f"{API_BASE_URL}/api/tasks/{chord_task_id}/status")
        response.raise_for_status()
        data = response.json()
        logging.info(f"  - Polling... current status: {data['status']}")
        if data["ready"]:
            if data["status"] == "SUCCESS":
                final_result = data.get("result")
                logging.info(f"SUCCESS: Chord task completed. Final result: {final_result}")
                if final_result and final_result.get("successful") == expected_count:
                    logging.info(f"✅ Verification PASSED: Successful count ({final_result.get('successful')}) matches expected count ({expected_count}).")
                    return True
                else:
                    logging.error(f"❌ Verification FAILED: Result mismatch. Got: {final_result}, Expected successful count: {expected_count}.")
                    return False
            else: # FAILURE
                logging.error(f"❌ Verification FAILED: Chord task reported status {data['status']}. Info: {data.get('error_info')}")
                return False
        time.sleep(POLL_INTERVAL_SECONDS)
    logging.error(f"❌ Verification FAILED: Timed out after {VERIFICATION_TIMEOUT_SECONDS} seconds.")
    return False

def main():
    logging.info("--- Starting E2E Parsing Verification Script (Corrected) ---")
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        reports = search_for_reports(client)
        if not reports: return

        orchestrator_task_id = trigger_pipeline(client, reports)
        if not orchestrator_task_id: return

        chord_task_id = get_chord_task_id(client, orchestrator_task_id)
        if not chord_task_id: return

        success = verify_final_result(client, chord_task_id, len(reports))
        if success:
            logging.info("✅ ✅ ✅ E2E PARSING VERIFICATION SUCCEEDED! ✅ ✅ ✅")
        else:
            logging.error("❌ ❌ ❌ E2E PARSING VERIFICATION FAILED! ❌ ❌ ❌")

if __name__ == "__main__":
    main()
