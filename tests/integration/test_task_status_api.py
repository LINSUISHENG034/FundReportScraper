"""
Integration tests for the Task Status API
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.main import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    app = create_app()
    return TestClient(app)


def test_get_task_status_success(client):
    """Test successful task status retrieval"""
    # Mock the AsyncResult
    with patch('src.api.routes.tasks.AsyncResult') as mock_async_result:
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.failed.return_value = False
        mock_result.get.return_value = {"successful": 1, "failed": 0}
        mock_async_result.return_value = mock_result
        
        response = client.get("/api/tasks/test-task-id/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "SUCCESS"
        assert data["ready"] is True
        assert data["result"] == {"successful": 1, "failed": 0}


def test_get_task_status_pending(client):
    """Test pending task status retrieval"""
    with patch('src.api.routes.tasks.AsyncResult') as mock_async_result:
        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_result.ready.return_value = False
        mock_result.successful.return_value = False
        mock_result.failed.return_value = False
        mock_async_result.return_value = mock_result
        
        response = client.get("/api/tasks/test-task-id/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "PENDING"
        assert data["ready"] is False
        assert data["result"] is None


def test_get_task_status_failed(client):
    """Test failed task status retrieval"""
    with patch('src.api.routes.tasks.AsyncResult') as mock_async_result:
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.failed.return_value = True
        mock_result.info = "Task failed due to error"
        mock_async_result.return_value = mock_result
        
        response = client.get("/api/tasks/test-task-id/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "FAILURE"
        assert data["ready"] is True
        assert data["error_info"] == "Task failed due to error"


def test_get_task_status_exception(client):
    """Test task status API when an exception occurs"""
    with patch('src.api.routes.tasks.AsyncResult') as mock_async_result:
        mock_async_result.side_effect = Exception("Redis connection failed")
        
        response = client.get("/api/tasks/test-task-id/status")
        
        assert response.status_code == 500
        data = response.json()
        assert "An unexpected error occurred while fetching task status" in data["detail"]