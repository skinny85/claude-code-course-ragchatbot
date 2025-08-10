import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import Config
from models import Course, CourseChunk, Lesson
from rag_system import RAGSystem


class TestRAGSystemIntegration:
    """Test RAG system end-to-end functionality"""

    def setup_method(self):
        """Setup test fixtures with temporary database"""
        self.temp_dir = tempfile.mkdtemp()

        # Create test config
        self.test_config = Config()
        self.test_config.CHROMA_PATH = self.temp_dir
        self.test_config.ANTHROPIC_API_KEY = "test-api-key"
        # Fix the MAX_RESULTS issue for testing
        self.test_config.MAX_RESULTS = 3

        self.rag_system = RAGSystem(self.test_config)

    def teardown_method(self):
        """Clean up temporary database"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rag_system_initialization(self):
        """Test that RAG system initializes all components correctly"""
        assert self.rag_system.config == self.test_config
        assert self.rag_system.document_processor is not None
        assert self.rag_system.vector_store is not None
        assert self.rag_system.ai_generator is not None
        assert self.rag_system.session_manager is not None
        assert self.rag_system.tool_manager is not None
        assert self.rag_system.search_tool is not None
        assert self.rag_system.outline_tool is not None

        # Verify tools are registered
        tool_definitions = self.rag_system.tool_manager.get_tool_definitions()
        tool_names = [tool["name"] for tool in tool_definitions]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names

    def test_add_course_document_success(self):
        """Test adding a course document successfully"""
        # Create a temporary course document
        course_content = """Course Title: Test Python Course
Course Link: https://example.com/python
Course Instructor: Test Instructor

Lesson 1: Python Basics
This is the content for Python basics lesson.
"""

        temp_file = os.path.join(self.temp_dir, "test_course.txt")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(course_content)

        course, chunk_count = self.rag_system.add_course_document(temp_file)

        assert course is not None
        assert course.title == "Test Python Course"
        assert course.instructor == "Test Instructor"
        assert course.course_link == "https://example.com/python"
        assert len(course.lessons) == 1
        assert course.lessons[0].lesson_number == 1
        assert course.lessons[0].title == "Python Basics"

        assert chunk_count > 0

        # Verify course was added to vector store
        existing_titles = self.rag_system.vector_store.get_existing_course_titles()
        assert "Test Python Course" in existing_titles

    def test_add_course_document_error_handling(self):
        """Test error handling when adding invalid course document"""
        nonexistent_file = "/path/that/does/not/exist.txt"

        course, chunk_count = self.rag_system.add_course_document(nonexistent_file)

        assert course is None
        assert chunk_count == 0

    def test_add_course_folder_success(self):
        """Test adding multiple course documents from folder"""
        # Create temporary folder with course documents
        docs_folder = os.path.join(self.temp_dir, "docs")
        os.makedirs(docs_folder)

        # Create first course document
        course1_content = """Course Title: Course A
Course Instructor: Instructor A

Lesson 1: Introduction
Content for course A lesson 1.
"""

        # Create second course document
        course2_content = """Course Title: Course B
Course Instructor: Instructor B

Lesson 1: Getting Started
Content for course B lesson 1.
"""

        with open(os.path.join(docs_folder, "course1.txt"), "w") as f:
            f.write(course1_content)

        with open(os.path.join(docs_folder, "course2.txt"), "w") as f:
            f.write(course2_content)

        courses_added, total_chunks = self.rag_system.add_course_folder(docs_folder)

        assert courses_added == 2
        assert total_chunks > 0

        # Verify both courses were added
        existing_titles = self.rag_system.vector_store.get_existing_course_titles()
        assert "Course A" in existing_titles
        assert "Course B" in existing_titles

    def test_add_course_folder_skip_existing(self):
        """Test that existing courses are skipped when adding folder"""
        docs_folder = os.path.join(self.temp_dir, "docs")
        os.makedirs(docs_folder)

        course_content = """Course Title: Existing Course
Course Instructor: Test

Lesson 1: Test
Content here.
"""

        with open(os.path.join(docs_folder, "course.txt"), "w") as f:
            f.write(course_content)

        # Add courses first time
        courses_added1, _ = self.rag_system.add_course_folder(docs_folder)
        assert courses_added1 == 1

        # Add same folder again - should skip existing
        courses_added2, _ = self.rag_system.add_course_folder(docs_folder)
        assert courses_added2 == 0

    def test_add_course_folder_nonexistent(self):
        """Test handling of non-existent folder"""
        courses_added, total_chunks = self.rag_system.add_course_folder(
            "/nonexistent/path"
        )

        assert courses_added == 0
        assert total_chunks == 0

    @patch("rag_system.AIGenerator")
    def test_query_without_session(self, mock_ai_generator_class):
        """Test query processing without session ID"""
        # Setup mock AI generator
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Test response"
        mock_ai_generator_class.return_value = mock_ai_generator

        # Create new RAG system with mocked AI generator
        rag_system = RAGSystem(self.test_config)
        rag_system.ai_generator = mock_ai_generator

        response, sources = rag_system.query("What is Python?")

        # Verify AI generator was called correctly
        mock_ai_generator.generate_response.assert_called_once()
        call_args = mock_ai_generator.generate_response.call_args

        assert "What is Python?" in call_args[1]["query"]
        assert call_args[1]["conversation_history"] is None
        assert call_args[1]["tools"] is not None
        assert call_args[1]["tool_manager"] is not None

        assert response == "Test response"
        assert isinstance(sources, list)

    @patch("rag_system.AIGenerator")
    def test_query_with_session(self, mock_ai_generator_class):
        """Test query processing with session ID"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Test response with history"
        mock_ai_generator_class.return_value = mock_ai_generator

        rag_system = RAGSystem(self.test_config)
        rag_system.ai_generator = mock_ai_generator

        # Create a session first
        session_id = rag_system.session_manager.create_session()
        rag_system.session_manager.add_exchange(
            session_id, "Previous question", "Previous answer"
        )

        response, sources = rag_system.query(
            "Follow-up question", session_id=session_id
        )

        # Verify conversation history was passed
        call_args = mock_ai_generator.generate_response.call_args
        assert call_args[1]["conversation_history"] is not None
        assert "Previous question" in call_args[1]["conversation_history"]

        assert response == "Test response with history"

    def test_query_sources_handling(self):
        """Test that sources are properly retrieved and reset"""
        # Mock the tool manager to return sources
        mock_sources = [{"text": "Source 1", "url": "https://example.com/1"}]
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=mock_sources)
        self.rag_system.tool_manager.reset_sources = Mock()

        # Mock AI generator to avoid actual API calls
        self.rag_system.ai_generator.generate_response = Mock(
            return_value="Test response"
        )

        response, sources = self.rag_system.query("Test query")

        # Verify sources were retrieved and reset
        self.rag_system.tool_manager.get_last_sources.assert_called_once()
        self.rag_system.tool_manager.reset_sources.assert_called_once()
        assert sources == mock_sources

    def test_get_course_analytics(self):
        """Test course analytics functionality"""
        # Add test course first
        course_content = """Course Title: Analytics Test Course
Course Instructor: Test

Lesson 1: Test
Test content.
"""

        temp_file = os.path.join(self.temp_dir, "analytics_test.txt")
        with open(temp_file, "w") as f:
            f.write(course_content)

        self.rag_system.add_course_document(temp_file)

        analytics = self.rag_system.get_course_analytics()

        assert "total_courses" in analytics
        assert "course_titles" in analytics
        assert analytics["total_courses"] == 1
        assert "Analytics Test Course" in analytics["course_titles"]


class TestRAGSystemWithRealData:
    """Test RAG system with real course data to identify actual issues"""

    def setup_method(self):
        """Setup with real course data from docs folder"""
        self.temp_dir = tempfile.mkdtemp()

        self.test_config = Config()
        self.test_config.CHROMA_PATH = self.temp_dir
        self.test_config.ANTHROPIC_API_KEY = "test-api-key"
        # This is the critical fix - MAX_RESULTS must be > 0
        self.test_config.MAX_RESULTS = 5

        self.rag_system = RAGSystem(self.test_config)

    def teardown_method(self):
        """Clean up"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_real_course_documents(self):
        """Test loading actual course documents from docs folder"""
        docs_path = (
            "/Users/adam_ruka/workplace/personal/claude-code-course/lessons-2-to-6/docs"
        )

        if os.path.exists(docs_path):
            courses_added, chunks_added = self.rag_system.add_course_folder(docs_path)

            assert courses_added > 0, "Should have loaded at least one course"
            assert chunks_added > 0, "Should have created at least one chunk"

            # Verify courses are searchable
            existing_titles = self.rag_system.vector_store.get_existing_course_titles()
            assert len(existing_titles) > 0, "Should have course titles available"

            print(f"Loaded {courses_added} courses with {chunks_added} total chunks")
            print(f"Course titles: {existing_titles}")
        else:
            pytest.skip("Real docs folder not available")

    def test_search_functionality_with_real_data(self):
        """Test search functionality with real course data"""
        docs_path = (
            "/Users/adam_ruka/workplace/personal/claude-code-course/lessons-2-to-6/docs"
        )

        if os.path.exists(docs_path):
            # Load real data
            self.rag_system.add_course_folder(docs_path)

            # Test direct vector store search
            search_results = self.rag_system.vector_store.search("computer use")

            print(f"Search results error: {search_results.error}")
            print(f"Number of documents found: {len(search_results.documents)}")
            print(f"Documents: {search_results.documents}")
            print(f"Metadata: {search_results.metadata}")

            if search_results.error:
                pytest.fail(f"Search failed with error: {search_results.error}")

            # Should find some results for common terms
            assert (
                not search_results.is_empty()
            ), "Search should find results for 'computer use'"

            # Test search tool
            tool_result = self.rag_system.search_tool.execute("computer use")
            print(f"Tool result: {tool_result}")

            assert (
                "No relevant content found" not in tool_result
            ), "Tool should find relevant content"
        else:
            pytest.skip("Real docs folder not available")

    def test_max_results_configuration_impact(self):
        """Test the impact of MAX_RESULTS configuration"""
        docs_path = (
            "/Users/adam_ruka/workplace/personal/claude-code-course/lessons-2-to-6/docs"
        )

        if os.path.exists(docs_path):
            # Test with MAX_RESULTS = 0 (the bug)
            buggy_config = Config()
            buggy_config.CHROMA_PATH = os.path.join(self.temp_dir, "buggy")
            buggy_config.ANTHROPIC_API_KEY = "test-api-key"
            buggy_config.MAX_RESULTS = 0  # This is the bug!

            buggy_rag = RAGSystem(buggy_config)
            buggy_rag.add_course_folder(docs_path)

            # Search with buggy config
            buggy_results = buggy_rag.vector_store.search("computer use")

            print(f"Buggy config results: {len(buggy_results.documents)} documents")

            # With MAX_RESULTS = 0, we should get 0 results even if content exists
            # This would be the root cause of "query failed" errors

            # Test with fixed config
            fixed_results = self.rag_system.vector_store.search("computer use")
            print(f"Fixed config results: {len(fixed_results.documents)} documents")

            # Fixed config should return more results
            assert len(fixed_results.documents) > len(
                buggy_results.documents
            ), "Fixed config should return more search results than buggy config"
        else:
            pytest.skip("Real docs folder not available")


if __name__ == "__main__":
    pytest.main([__file__])
