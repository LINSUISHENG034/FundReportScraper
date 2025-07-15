"""
API Route for querying the status of Celery tasks.
"""
from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from src.core.celery_app import app as celery_app
from src.core.logging import get_logger

router = APIRouter(prefix="/api")
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
            task_return_value = task_result.get()
            response_data["result"] = task_return_value
            
            # If this is a start_download_pipeline task, also return the chord_task_id
            if isinstance(task_return_value, dict) and "chord_task_id" in task_return_value:
                response_data["chord_task_id"] = task_return_value["chord_task_id"]
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