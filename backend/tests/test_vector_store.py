import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from models import Course, CourseChunk, Lesson
from vector_store import SearchResults, VectorStore


class TestSearchResults:
    """Test SearchResults utility class"""

    def test_from_chroma_with_results(self):
        """Test creating SearchResults from ChromaDB results"""
        chroma_results = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"meta1": "value1"}, {"meta2": "value2"}]],
            "distances": [[0.1, 0.2]],
        }

        results = SearchResults.from_chroma(chroma_results)

        assert results.documents == ["doc1", "doc2"]
        assert results.metadata == [{"meta1": "value1"}, {"meta2": "value2"}]
        assert results.distances == [0.1, 0.2]
        assert results.error is None

    def test_from_chroma_empty(self):
        """Test creating SearchResults from empty ChromaDB results"""
        chroma_results = {"documents": [], "metadatas": [], "distances": []}

        results = SearchResults.from_chroma(chroma_results)

        assert results.documents == []
        assert results.metadata == []
        assert results.distances == []
        assert results.error is None

    def test_empty_with_error(self):
        """Test creating empty SearchResults with error"""
        results = SearchResults.empty("Test error")

        assert results.documents == []
        assert results.metadata == []
        assert results.distances == []
        assert results.error == "Test error"

    def test_is_empty(self):
        """Test empty detection"""
        empty_results = SearchResults([], [], [])
        non_empty_results = SearchResults(["doc"], [{"meta": "value"}], [0.1])

        assert empty_results.is_empty() is True
        assert non_empty_results.is_empty() is False


class TestVectorStore:
    """Test VectorStore functionality"""

    def setup_method(self):
        """Setup test fixtures with temporary database"""
        self.temp_dir = tempfile.mkdtemp()
        self.vector_store = VectorStore(
            chroma_path=self.temp_dir, embedding_model="all-MiniLM-L6-v2", max_results=3
        )

    def teardown_method(self):
        """Clean up temporary database"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Test VectorStore initialization"""
        assert self.vector_store.max_results == 3
        assert self.vector_store.client is not None
        assert self.vector_store.course_catalog is not None
        assert self.vector_store.course_content is not None

    def test_add_course_metadata(self):
        """Test adding course metadata"""
        course = Course(
            title="Test Course",
            course_link="https://example.com/course",
            instructor="Test Instructor",
            lessons=[
                Lesson(
                    lesson_number=1,
                    title="Introduction",
                    lesson_link="https://example.com/lesson1",
                ),
                Lesson(lesson_number=2, title="Advanced Topics"),
            ],
        )

        # This should not raise an exception
        self.vector_store.add_course_metadata(course)

        # Verify course was added
        results = self.vector_store.course_catalog.get(ids=["Test Course"])
        assert results is not None
        assert len(results["ids"]) == 1
        assert results["ids"][0] == "Test Course"

    def test_add_course_content(self):
        """Test adding course content chunks"""
        chunks = [
            CourseChunk(
                content="This is lesson 1 content",
                course_title="Test Course",
                lesson_number=1,
                chunk_index=0,
            ),
            CourseChunk(
                content="This is lesson 2 content",
                course_title="Test Course",
                lesson_number=2,
                chunk_index=1,
            ),
        ]

        # This should not raise an exception
        self.vector_store.add_course_content(chunks)

        # Verify chunks were added
        results = self.vector_store.course_content.get()
        assert len(results["ids"]) == 2

    def test_add_empty_course_content(self):
        """Test adding empty course content list"""
        # Should handle gracefully without errors
        self.vector_store.add_course_content([])

        results = self.vector_store.course_content.get()
        assert len(results["ids"]) == 0

    @patch("vector_store.chromadb")
    def test_search_with_mock_results(self, mock_chromadb):
        """Test search functionality with mocked ChromaDB"""
        # Mock ChromaDB collections
        mock_content_collection = Mock()
        mock_content_collection.query.return_value = {
            "documents": [["Test content about Python"]],
            "metadatas": [[{"course_title": "Python 101", "lesson_number": 1}]],
            "distances": [[0.1]],
        }

        self.vector_store.course_content = mock_content_collection

        results = self.vector_store.search("Python programming")

        # Verify search was called correctly
        mock_content_collection.query.assert_called_once_with(
            query_texts=["Python programming"], n_results=3, where=None
        )

        # Verify results
        assert len(results.documents) == 1
        assert results.documents[0] == "Test content about Python"
        assert results.metadata[0]["course_title"] == "Python 101"
        assert results.error is None

    def test_search_with_course_filter(self):
        """Test search with course name filter"""
        # Add test data first
        course = Course(title="Python Programming", lessons=[])
        self.vector_store.add_course_metadata(course)

        chunk = CourseChunk(
            content="Python variables and functions",
            course_title="Python Programming",
            lesson_number=1,
            chunk_index=0,
        )
        self.vector_store.add_course_content([chunk])

        # Mock the course name resolution to return exact match
        with patch.object(
            self.vector_store, "_resolve_course_name", return_value="Python Programming"
        ):
            results = self.vector_store.search("variables", course_name="Python")

        # Should have called search with course filter
        assert results.error is None

    def test_search_course_not_found(self):
        """Test search when course name doesn't resolve"""
        with patch.object(self.vector_store, "_resolve_course_name", return_value=None):
            results = self.vector_store.search("test", course_name="Nonexistent")

        assert results.error == "No course found matching 'Nonexistent'"
        assert results.is_empty()

    def test_search_exception_handling(self):
        """Test search error handling"""
        # Mock collection to raise exception
        mock_content_collection = Mock()
        mock_content_collection.query.side_effect = Exception("Database error")
        self.vector_store.course_content = mock_content_collection

        results = self.vector_store.search("test query")

        assert results.error == "Search error: Database error"
        assert results.is_empty()

    def test_resolve_course_name(self):
        """Test course name resolution"""
        # Add test course
        course = Course(title="Advanced Python Programming", lessons=[])
        self.vector_store.add_course_metadata(course)

        # Should find course with partial match
        resolved = self.vector_store._resolve_course_name("Python")
        assert resolved == "Advanced Python Programming"

    def test_resolve_course_name_not_found(self):
        """Test course name resolution when not found"""
        resolved = self.vector_store._resolve_course_name("Nonexistent Course")
        assert resolved is None

    def test_build_filter_no_params(self):
        """Test filter building with no parameters"""
        filter_dict = self.vector_store._build_filter(None, None)
        assert filter_dict is None

    def test_build_filter_course_only(self):
        """Test filter building with course only"""
        filter_dict = self.vector_store._build_filter("Python 101", None)
        assert filter_dict == {"course_title": "Python 101"}

    def test_build_filter_lesson_only(self):
        """Test filter building with lesson only"""
        filter_dict = self.vector_store._build_filter(None, 2)
        assert filter_dict == {"lesson_number": 2}

    def test_build_filter_both_params(self):
        """Test filter building with both course and lesson"""
        filter_dict = self.vector_store._build_filter("Python 101", 2)
        assert filter_dict == {
            "$and": [{"course_title": "Python 101"}, {"lesson_number": 2}]
        }

    def test_get_existing_course_titles(self):
        """Test getting existing course titles"""
        # Add test courses
        course1 = Course(title="Course A", lessons=[])
        course2 = Course(title="Course B", lessons=[])
        self.vector_store.add_course_metadata(course1)
        self.vector_store.add_course_metadata(course2)

        titles = self.vector_store.get_existing_course_titles()

        assert "Course A" in titles
        assert "Course B" in titles
        assert len(titles) == 2

    def test_get_course_count(self):
        """Test getting course count"""
        # Add test courses
        course1 = Course(title="Course A", lessons=[])
        course2 = Course(title="Course B", lessons=[])
        self.vector_store.add_course_metadata(course1)
        self.vector_store.add_course_metadata(course2)

        count = self.vector_store.get_course_count()
        assert count == 2

    def test_get_course_link(self):
        """Test getting course link"""
        course = Course(
            title="Test Course", course_link="https://example.com/course", lessons=[]
        )
        self.vector_store.add_course_metadata(course)

        link = self.vector_store.get_course_link("Test Course")
        assert link == "https://example.com/course"

    def test_get_course_link_not_found(self):
        """Test getting course link for non-existent course"""
        link = self.vector_store.get_course_link("Nonexistent Course")
        assert link is None

    def test_get_lesson_link(self):
        """Test getting lesson link"""
        course = Course(
            title="Test Course",
            lessons=[
                Lesson(
                    lesson_number=1,
                    title="Introduction",
                    lesson_link="https://example.com/lesson1",
                ),
                Lesson(
                    lesson_number=2,
                    title="Advanced",
                    lesson_link="https://example.com/lesson2",
                ),
            ],
        )
        self.vector_store.add_course_metadata(course)

        link = self.vector_store.get_lesson_link("Test Course", 1)
        assert link == "https://example.com/lesson1"

        link = self.vector_store.get_lesson_link("Test Course", 2)
        assert link == "https://example.com/lesson2"

    def test_get_lesson_link_not_found(self):
        """Test getting lesson link for non-existent lesson"""
        course = Course(title="Test Course", lessons=[])
        self.vector_store.add_course_metadata(course)

        link = self.vector_store.get_lesson_link("Test Course", 999)
        assert link is None

    def test_clear_all_data(self):
        """Test clearing all data"""
        # Add some test data
        course = Course(title="Test Course", lessons=[])
        self.vector_store.add_course_metadata(course)

        chunk = CourseChunk(
            content="Test content",
            course_title="Test Course",
            lesson_number=1,
            chunk_index=0,
        )
        self.vector_store.add_course_content([chunk])

        # Clear data
        self.vector_store.clear_all_data()

        # Verify data is cleared
        catalog_results = self.vector_store.course_catalog.get()
        content_results = self.vector_store.course_content.get()

        assert len(catalog_results["ids"]) == 0
        assert len(content_results["ids"]) == 0

    def test_get_all_courses_metadata(self):
        """Test getting all courses metadata"""
        course = Course(
            title="Test Course",
            instructor="Test Instructor",
            course_link="https://example.com/course",
            lessons=[Lesson(lesson_number=1, title="Introduction")],
        )
        self.vector_store.add_course_metadata(course)

        metadata = self.vector_store.get_all_courses_metadata()

        assert len(metadata) == 1
        assert metadata[0]["title"] == "Test Course"
        assert metadata[0]["instructor"] == "Test Instructor"
        assert metadata[0]["course_link"] == "https://example.com/course"
        assert "lessons" in metadata[0]
        assert len(metadata[0]["lessons"]) == 1


if __name__ == "__main__":
    pytest.main([__file__])
