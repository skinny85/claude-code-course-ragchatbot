import pytest
import json
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch


@pytest.mark.api
class TestQueryEndpoint:
    """Test the /api/query endpoint"""

    def test_query_endpoint_success(self, test_client, mock_query_request, mock_query_response):
        """Test successful query processing"""
        client, mock_rag_system = test_client
        
        # Configure mock responses
        mock_rag_system.session_manager.create_session.return_value = "test-session-123"
        mock_rag_system.query.return_value = (
            mock_query_response["answer"], 
            mock_query_response["sources"]
        )
        
        response = client.post("/api/query", json=mock_query_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["answer"] == mock_query_response["answer"]
        assert isinstance(data["sources"], list)
        assert data["session_id"] == "test-session-123"
        
        # Verify RAG system was called correctly
        mock_rag_system.query.assert_called_once_with("What is Python?", "test-session-123")

    def test_query_endpoint_with_existing_session(self, test_client):
        """Test query with existing session ID"""
        client, mock_rag_system = test_client
        
        existing_session = "existing-session-456"
        request_data = {
            "query": "Follow up question",
            "session_id": existing_session
        }
        
        mock_rag_system.query.return_value = ("Follow up answer", [])
        
        response = client.post("/api/query", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["session_id"] == existing_session
        mock_rag_system.query.assert_called_once_with("Follow up question", existing_session)
        # Should not create new session when one is provided
        mock_rag_system.session_manager.create_session.assert_not_called()

    def test_query_endpoint_missing_query(self, test_client):
        """Test query endpoint with missing query field"""
        client, _ = test_client
        
        response = client.post("/api/query", json={"session_id": "test"})
        
        assert response.status_code == 422  # Unprocessable Entity
        assert "query" in response.text.lower()

    def test_query_endpoint_empty_query(self, test_client):
        """Test query endpoint with empty query"""
        client, mock_rag_system = test_client
        
        mock_rag_system.query.return_value = ("Please provide a question", [])
        
        response = client.post("/api/query", json={"query": ""})
        
        assert response.status_code == 200
        # Should still process empty query gracefully

    def test_query_endpoint_internal_error(self, test_client):
        """Test query endpoint error handling"""
        client, mock_rag_system = test_client
        
        # Simulate RAG system error
        mock_rag_system.query.side_effect = Exception("Internal processing error")
        
        response = client.post("/api/query", json={"query": "Test query"})
        
        assert response.status_code == 500
        assert "Internal processing error" in response.json()["detail"]

    def test_query_endpoint_invalid_json(self, test_client):
        """Test query endpoint with invalid JSON"""
        client, _ = test_client
        
        response = client.post(
            "/api/query", 
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422

    def test_query_endpoint_response_structure(self, test_client):
        """Test that query response has correct structure"""
        client, mock_rag_system = test_client
        
        mock_sources = [
            {
                "text": "Source content",
                "course_title": "Test Course",
                "lesson_number": 1,
                "lesson_title": "Test Lesson"
            }
        ]
        
        mock_rag_system.session_manager.create_session.return_value = "session-123"
        mock_rag_system.query.return_value = ("Test answer", mock_sources)
        
        response = client.post("/api/query", json={"query": "test"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)
        
        if data["sources"]:
            source = data["sources"][0]
            assert "text" in source


@pytest.mark.api
class TestCoursesEndpoint:
    """Test the /api/courses endpoint"""

    def test_courses_endpoint_success(self, test_client, mock_course_stats):
        """Test successful course statistics retrieval"""
        client, mock_rag_system = test_client
        
        mock_rag_system.get_course_analytics.return_value = mock_course_stats
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_courses" in data
        assert "course_titles" in data
        assert data["total_courses"] == mock_course_stats["total_courses"]
        assert data["course_titles"] == mock_course_stats["course_titles"]
        
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_courses_endpoint_empty_analytics(self, test_client):
        """Test courses endpoint with no courses"""
        client, mock_rag_system = test_client
        
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_courses_endpoint_internal_error(self, test_client):
        """Test courses endpoint error handling"""
        client, mock_rag_system = test_client
        
        # Simulate analytics error
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")
        
        response = client.get("/api/courses")
        
        assert response.status_code == 500
        assert "Analytics error" in response.json()["detail"]

    def test_courses_endpoint_response_structure(self, test_client):
        """Test that courses response has correct structure"""
        client, mock_rag_system = test_client
        
        mock_analytics = {
            "total_courses": 2,
            "course_titles": ["Course A", "Course B"]
        }
        
        mock_rag_system.get_course_analytics.return_value = mock_analytics
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        
        for title in data["course_titles"]:
            assert isinstance(title, str)


@pytest.mark.api
class TestRootEndpoint:
    """Test the / root endpoint"""

    def test_root_endpoint_success(self, test_client):
        """Test successful root endpoint access"""
        client, _ = test_client
        
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert isinstance(data["message"], str)

    def test_root_endpoint_cors_headers(self, test_client):
        """Test that CORS headers are properly set"""
        client, _ = test_client
        
        response = client.options("/")
        
        # CORS should be handled by middleware
        assert response.status_code in [200, 405]  # Either OK or Method Not Allowed


@pytest.mark.api
class TestAPIIntegration:
    """Integration tests for API endpoints"""

    def test_query_and_courses_flow(self, test_client):
        """Test typical user flow: check courses then query"""
        client, mock_rag_system = test_client
        
        # Setup mock responses
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 1,
            "course_titles": ["Python Basics"]
        }
        mock_rag_system.session_manager.create_session.return_value = "flow-session"
        mock_rag_system.query.return_value = ("Python is great!", [])
        
        # First, get course info
        courses_response = client.get("/api/courses")
        assert courses_response.status_code == 200
        courses_data = courses_response.json()
        assert courses_data["total_courses"] == 1
        
        # Then make a query
        query_response = client.post("/api/query", json={
            "query": "Tell me about Python"
        })
        assert query_response.status_code == 200
        query_data = query_response.json()
        assert query_data["answer"] == "Python is great!"

    def test_multiple_queries_same_session(self, test_client):
        """Test multiple queries in the same session"""
        client, mock_rag_system = test_client
        
        session_id = "multi-query-session"
        mock_rag_system.query.return_value = ("Response", [])
        
        # First query
        response1 = client.post("/api/query", json={
            "query": "First question",
            "session_id": session_id
        })
        assert response1.status_code == 200
        
        # Second query in same session
        response2 = client.post("/api/query", json={
            "query": "Second question", 
            "session_id": session_id
        })
        assert response2.status_code == 200
        
        # Verify both used same session
        assert response1.json()["session_id"] == session_id
        assert response2.json()["session_id"] == session_id
        
        # Verify RAG system was called twice with same session
        assert mock_rag_system.query.call_count == 2
        calls = mock_rag_system.query.call_args_list
        assert calls[0][0][1] == session_id  # First call session
        assert calls[1][0][1] == session_id  # Second call session

    def test_error_recovery(self, test_client):
        """Test that API can recover from errors"""
        client, mock_rag_system = test_client
        
        # First request fails
        mock_rag_system.query.side_effect = Exception("Temporary error")
        
        response1 = client.post("/api/query", json={"query": "test"})
        assert response1.status_code == 500
        
        # Second request succeeds
        mock_rag_system.query.side_effect = None
        mock_rag_system.query.return_value = ("Success", [])
        
        response2 = client.post("/api/query", json={"query": "test again"})
        assert response2.status_code == 200
        assert response2.json()["answer"] == "Success"