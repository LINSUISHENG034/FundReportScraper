"""
Phase 4.5 End-to-End Verification Script

This script performs a real-world test of the refactored backend by:
1. Searching for a specific, small set of fund reports via the API.
2. Triggering a download task for these reports via the API.
3. Verifying that the corresponding files are downloaded and saved correctly.

This serves as the final quality gate before proceeding to Phase 5.
"""

import asyncio
import httpx
import logging
import time
from pathlib import Path
from typing import List, Dict, Any

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"
DOWNLOAD_DIR = Path("data/downloads/e2e_verification")
VERIFICATION_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 5

# --- Test Target ---
# We will search for a single fund's Q1 2025 report.
# This provides a small, predictable, and fast test case.
TARGET_YEAR = 2024
TARGET_REPORT_TYPE = "FB010010"  
TARGET_FUND_CODE = "015975"      # A known fund from test fixtures

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

async def search_for_reports(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Step 1: Search for the target reports via the API."""
    logging.info(f"STEP 1: Searching for reports...")
    logging.info(f"  - Year: {TARGET_YEAR}")
    logging.info(f"  - Report Type: {TARGET_REPORT_TYPE}")
    logging.info(f"  - Fund Code: {TARGET_FUND_CODE}")

    params = {
        "year": TARGET_YEAR,
        "report_type": TARGET_REPORT_TYPE,
        "fund_code": TARGET_FUND_CODE,
    }
    try:
        response = await client.get(f"{API_BASE_URL}/api/reports", params=params)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes

        data = response.json()
        if not data.get("success") or not data.get("data"):
            logging.error(f"API search failed or returned no data. Response: {data}")
            return []

        reports = data["data"]
        logging.info(f"SUCCESS: Found {len(reports)} report(s) to download.")
        for report in reports:
            logging.info(f"  - Found Report: upload_info_id={report['upload_info_id']}, name={report['fund_short_name']}")
        return reports
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error during search: {e.response.status_code} - {e.response.text}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred during search: {e}")
        return []

async def trigger_download(client: httpx.AsyncClient, reports: List[Dict[str, Any]]) -> str:
    """Step 2: Trigger a download task for the found reports."""
    logging.info("STEP 2: Triggering download task...")
    
    # The API now expects the full list of report objects, not just their IDs.
    payload = {
        "reports": reports,
        "save_dir": str(DOWNLOAD_DIR)
    }
    try:
        response = await client.post(f"{API_BASE_URL}/api/downloads", json=payload)
        response.raise_for_status()

        data = response.json()
        if not data.get("success"):
            logging.error(f"API call to trigger download failed. Response: {data}")
            return ""
        
        task_id = data["task_id"]
        logging.info(f"SUCCESS: Download task created. Task ID: {task_id}")
        return task_id
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error during download trigger: {e.response.status_code} - {e.response.text}")
        return ""
    except Exception as e:
        logging.error(f"An unexpected error occurred during download trigger: {e}")
        return ""

def verify_downloads(reports: List[Dict[str, Any]]) -> bool:
    """Step 3: Poll the download directory to verify file creation."""
    logging.info("STEP 3: Verifying downloaded files...")
    
    expected_files = [
        DOWNLOAD_DIR / f"{r['fund_code']}_{r['upload_info_id']}.xbrl" for r in reports
    ]
    
    logging.info("Expected files:")
    for f in expected_files:
        logging.info(f"  - {f}")

    start_time = time.time()
    while time.time() - start_time < VERIFICATION_TIMEOUT_SECONDS:
        all_found = True
        for file_path in expected_files:
            if not file_path.exists():
                all_found = False
                break
        
        if all_found:
            logging.info("SUCCESS: All expected files have been found in the download directory.")
            return True
        
        logging.info(f"Verification in progress... waiting for files. Retrying in {POLL_INTERVAL_SECONDS}s.")
        time.sleep(POLL_INTERVAL_SECONDS)

    logging.error(f"FAILURE: Verification timed out after {VERIFICATION_TIMEOUT_SECONDS} seconds.")
    logging.error("The following files were NOT found:")
    for file_path in expected_files:
        if not file_path.exists():
            logging.error(f"  - {file_path}")
    return False

async def main():
    """Main execution function."""
    logging.info("--- Starting E2E Verification Script for Phase 4.5 ---")
    
    # Ensure download directory exists
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient() as client:
        # Step 1
        reports_to_download = await search_for_reports(client)
        if not reports_to_download:
            logging.error("Verification failed at Step 1: Could not find reports to download.")
            return

        # Step 2
        task_id = await trigger_download(client, reports_to_download)
        if not task_id:
            logging.error("Verification failed at Step 2: Could not trigger download task.")
            return
            
        # Step 3
        # This part is synchronous as it involves polling the file system.
        verification_success = verify_downloads(reports_to_download)
        if not verification_success:
            logging.error("Verification failed at Step 3: Files were not downloaded correctly.")
            return

    logging.info("----------------------------------------------------")
    logging.info("✅ ✅ ✅  E2E VERIFICATION SUCCEEDED! ✅ ✅ ✅")
    logging.info("The backend can successfully search, download, and save reports.")
    logging.info("----------------------------------------------------")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\nVerification script cancelled by user.")
