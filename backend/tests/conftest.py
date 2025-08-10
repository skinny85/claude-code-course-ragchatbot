import pytest
import tempfile
import shutil
import os
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import Config
from rag_system import RAGSystem


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration"""
    config = Config()
    config.CHROMA_PATH = temp_dir
    config.ANTHROPIC_API_KEY = "test-api-key"
    config.MAX_RESULTS = 3
    return config


@pytest.fixture
def mock_rag_system(test_config):
    """Create a mocked RAG system for testing"""
    with patch('rag_system.AIGenerator') as mock_ai_gen:
        mock_ai_gen.return_value.generate_response.return_value = "Test response"
        rag_system = RAGSystem(test_config)
        rag_system.ai_generator.generate_response = Mock(return_value="Test response")
        yield rag_system


@pytest.fixture
def sample_course_content():
    """Sample course content for testing"""
    return """Course Title: Test Python Course
Course Link: https://example.com/python
Course Instructor: Test Instructor

Lesson 1: Python Basics
This is the content for Python basics lesson.
Learn about variables, data types, and control structures.

Lesson 2: Advanced Python
This lesson covers advanced topics like decorators and generators.
"""


@pytest.fixture
def sample_course_file(temp_dir, sample_course_content):
    """Create a sample course file for testing"""
    file_path = os.path.join(temp_dir, "test_course.txt")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(sample_course_content)
    return file_path


@pytest.fixture
def test_app():
    """Create a test FastAPI app without static file mounting"""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional, Dict, Any
    from unittest.mock import Mock
    
    # Create test app
    app = FastAPI(title="Test Course Materials RAG System")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mock RAG system
    mock_rag_system = Mock()
    mock_rag_system.session_manager.create_session.return_value = "test-session-id"
    mock_rag_system.query.return_value = ("Test response", [{"text": "Test source"}])
    mock_rag_system.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Test Course 1", "Test Course 2"]
    }
    
    # Pydantic models
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, Any]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]
    
    # API endpoints
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id or mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/")
    async def read_root():
        return {"message": "Course Materials RAG System"}
    
    return app, mock_rag_system


@pytest.fixture
def test_client(test_app):
    """Create a test client for the FastAPI app"""
    app, mock_rag_system = test_app
    client = TestClient(app)
    return client, mock_rag_system


@pytest.fixture
def mock_query_request():
    """Sample query request for testing"""
    return {
        "query": "What is Python?",
        "session_id": None
    }


@pytest.fixture
def mock_query_response():
    """Sample query response for testing"""
    return {
        "answer": "Python is a programming language",
        "sources": [
            {
                "text": "Python is a high-level programming language",
                "course_title": "Python Basics",
                "lesson_number": 1,
                "lesson_title": "Introduction"
            }
        ],
        "session_id": "test-session-123"
    }


@pytest.fixture
def mock_course_stats():
    """Sample course statistics for testing"""
    return {
        "total_courses": 3,
        "course_titles": [
            "Python Fundamentals",
            "Advanced Python",
            "Web Development with Flask"
        ]
    }