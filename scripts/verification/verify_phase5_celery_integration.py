import requests
import time
import json
import subprocess
import sys
import os

# API and script configuration
BASE_URL = "http://127.0.0.1:8000"
SEARCH_API_URL = f"{BASE_URL}/api/v2/reports"
DOWNLOAD_API_URL = f"{BASE_URL}/api/v2/downloads"
PYTHON_EXEC = sys.executable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def print_step(message):
    print(f"\n{'='*10} {message} {'='*10}")

def wait_for_server_ready(url, timeout=60):
    """Polls the server's health check endpoint until it's ready."""
    print_step(f"Waiting for server at {url} to be ready...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Server is ready.")
                return True
        except requests.ConnectionError:
            # Server is not up yet, wait and retry
            pass
        time.sleep(2)
    print(f"Error: Server at {url} did not become ready within {timeout} seconds.")
    return False

def run_e2e_test():
    # Step 1: Search for reports
    report_ids = search_for_reports()
    if not report_ids:
        return

    # Step 2: Create download task
    task_id = create_download_task(report_ids)
    if not task_id:
        return

    # Step 3: Poll task status
    poll_task_status(task_id)

def search_for_reports():
    """Step 1: Search for some reports to get their IDs."""
    print_step("Step 1: Searching for reports")
    # V2 search endpoint is GET /api/v2/reports
    search_url_v2 = f"{BASE_URL}/api/v2/reports"
    search_params = {
        "year": "2023",
        "report_type": "FB030040",  # Use the actual value for Q4
        "fund_company_short_name": "平安基金"
    }
    try:
        # V2 uses GET with query parameters
        response = requests.get(search_url_v2, params=search_params)
        response.raise_for_status()
        data = response.json()
        # V2 response structure is {"data": [...]}
        reports = data.get('data', [])
        if not reports:
            print("Error: No reports found.")
            return None
        
        report_ids = [report['upload_info_id'] for report in reports[:5]] # Get first 5
        print(f"Found {len(reports)} reports. Will use IDs: {report_ids}")
        return report_ids
    except requests.exceptions.RequestException as e:
        print(f"Error searching for reports: {e}")
        return None

def create_download_task(report_ids):
    """Step 2: Create a download task via API."""
    print_step("Step 2: Creating download task")
    if not report_ids:
        print("No report IDs to create a task.")
        return None
    
    download_payload = {
        "report_ids": report_ids
    }
    try:
        response = requests.post(DOWNLOAD_API_URL, json=download_payload)
        response.raise_for_status()
        data = response.json()
        task_id = data.get('task_id')
        if not task_id:
            print("Error: API did not return a task_id.")
            return None
        
        print(f"Successfully created download task. Task ID: {task_id}")
        return task_id
    except requests.exceptions.RequestException as e:
        print(f"Error creating download task: {e}")
        return None

def poll_task_status(task_id):
    """Step 3: Poll for the task status until it's completed or failed."""
    print_step(f"Step 3: Polling status for task {task_id}")
    if not task_id:
        print("No task ID to poll.")
        return

    while True:
        try:
            response = requests.get(f"{DOWNLOAD_API_URL}/{task_id}")
            response.raise_for_status()
            data = response.json()
            status_info = data.get('task_status', {})
            status = status_info.get('status')

            print(f"Current status: {status} | Progress: {status_info.get('progress', {}).get('percentage', 0)}%")

            if status in ["COMPLETED", "FAILED"]:
                print_step("Final Task Status")
                print(json.dumps(status_info, indent=2, ensure_ascii=False))
                break
            
            time.sleep(5)

        except requests.exceptions.RequestException as e:
            print(f"Error polling task status: {e}")
            break
        except KeyboardInterrupt:
            print("\nPolling stopped by user.")
            break

def cleanup_services(pids):
    """Terminate all running services based on their PIDs."""
    print_step("Cleaning up services")
    for service, pid in pids.items():
        try:
            proc = subprocess.Popen(['taskkill', '/F', '/T', '/PID', str(pid)])
            proc.wait(timeout=10)
            print(f"{service} (PID: {pid}) terminated.")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"Error terminating {service} (PID: {pid}): {e}")

def main():
    """Main function to manage services and run the E2E test."""
    print_step("Starting Phase 5 Celery Integration Verification")

    pids = {}
    log_files = {
        "celery": os.path.join(PROJECT_ROOT, "celery_worker.log"),
        "fastapi": os.path.join(PROJECT_ROOT, "fastapi_server.log")
    }

    try:
        # Start Celery Worker and log to file
        print_step("Starting Celery Worker")
        with open(log_files["celery"], 'wb') as celery_log:
            celery_command = [PYTHON_EXEC, "-m", "celery", "-A", "src.core.celery_app", "worker", "--loglevel=info"]
            celery_worker = subprocess.Popen(celery_command, cwd=PROJECT_ROOT, stdout=celery_log, stderr=subprocess.STDOUT)
            pids["celery"] = celery_worker.pid
            print(f"Celery Worker started with PID {celery_worker.pid}. Log: {log_files['celery']}")
        time.sleep(5)

        # Start FastAPI Server and log to file
        print_step("Starting FastAPI Server")
        with open(log_files["fastapi"], 'wb') as fastapi_log:
            fastapi_command = [PYTHON_EXEC, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8000"]
            fastapi_server = subprocess.Popen(fastapi_command, cwd=PROJECT_ROOT, stdout=fastapi_log, stderr=subprocess.STDOUT)
            pids["fastapi"] = fastapi_server.pid
            print(f"FastAPI Server started with PID {fastapi_server.pid}. Log: {log_files['fastapi']}")

        # Wait for the server to be ready
        if not wait_for_server_ready(f"{BASE_URL}/health"):
            raise RuntimeError("FastAPI server failed to start.")

        # Run the E2E test
        run_e2e_test()

    except Exception as e:
        print(f"An error occurred during the test run: {e}")
    finally:
        cleanup_services(pids)
        print_step("Verification script finished.")

if __name__ == "__main__":
    main()