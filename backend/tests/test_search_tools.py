import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test the CourseSearchTool execute method functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_vector_store = Mock()
        self.search_tool = CourseSearchTool(self.mock_vector_store)
    
    def test_execute_successful_search(self):
        """Test successful search with results"""
        # Mock successful search results
        mock_results = SearchResults(
            documents=["Course content about Python basics", "More Python content"],
            metadata=[
                {"course_title": "Python 101", "lesson_number": 1},
                {"course_title": "Python 101", "lesson_number": 2}
            ],
            distances=[0.1, 0.2]
        )
        self.mock_vector_store.search.return_value = mock_results
        
        # Execute search
        result = self.search_tool.execute("Python basics")
        
        # Verify search was called correctly
        self.mock_vector_store.search.assert_called_once_with(
            query="Python basics",
            course_name=None,
            lesson_number=None
        )
        
        # Verify results formatting
        assert "[Python 101 - Lesson 1]" in result
        assert "[Python 101 - Lesson 2]" in result
        assert "Course content about Python basics" in result
        assert "More Python content" in result
        
        # Verify sources are tracked
        assert len(self.search_tool.last_sources) == 2
        assert self.search_tool.last_sources[0]["text"] == "Python 101 - Lesson 1"
    
    def test_execute_with_course_filter(self):
        """Test search with course name filter"""
        mock_results = SearchResults(
            documents=["Course content"],
            metadata=[{"course_title": "Advanced Python", "lesson_number": 3}],
            distances=[0.1]
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("functions", course_name="Advanced Python")
        
        self.mock_vector_store.search.assert_called_once_with(
            query="functions",
            course_name="Advanced Python",
            lesson_number=None
        )
        assert "[Advanced Python - Lesson 3]" in result
    
    def test_execute_with_lesson_filter(self):
        """Test search with lesson number filter"""
        mock_results = SearchResults(
            documents=["Lesson 2 content"],
            metadata=[{"course_title": "Python 101", "lesson_number": 2}],
            distances=[0.1]
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("variables", lesson_number=2)
        
        self.mock_vector_store.search.assert_called_once_with(
            query="variables",
            course_name=None,
            lesson_number=2
        )
        assert "[Python 101 - Lesson 2]" in result
    
    def test_execute_empty_results(self):
        """Test handling of empty search results"""
        mock_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("nonexistent topic")
        
        assert result == "No relevant content found."
        assert len(self.search_tool.last_sources) == 0
    
    def test_execute_empty_results_with_filters(self):
        """Test empty results with filter information"""
        mock_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute(
            "nonexistent", 
            course_name="Test Course", 
            lesson_number=1
        )
        
        assert "No relevant content found in course 'Test Course' in lesson 1." in result
    
    def test_execute_search_error(self):
        """Test handling of search errors"""
        mock_results = SearchResults(
            documents=[], 
            metadata=[], 
            distances=[], 
            error="ChromaDB connection failed"
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("test query")
        
        assert result == "ChromaDB connection failed"
        assert len(self.search_tool.last_sources) == 0
    
    def test_execute_with_lesson_links(self):
        """Test that lesson links are retrieved and included in sources"""
        mock_results = SearchResults(
            documents=["Course content"],
            metadata=[{"course_title": "Python 101", "lesson_number": 1}],
            distances=[0.1]
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson1"
        
        result = self.search_tool.execute("Python")
        
        # Verify lesson link was requested
        self.mock_vector_store.get_lesson_link.assert_called_once_with("Python 101", 1)
        
        # Verify source includes the link
        assert len(self.search_tool.last_sources) == 1
        assert self.search_tool.last_sources[0]["url"] == "https://example.com/lesson1"
    
    def test_execute_lesson_link_error(self):
        """Test handling of lesson link retrieval errors"""
        mock_results = SearchResults(
            documents=["Course content"],
            metadata=[{"course_title": "Python 101", "lesson_number": 1}],
            distances=[0.1]
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.side_effect = Exception("Link fetch failed")
        
        # Should not raise exception, just print error and continue
        result = self.search_tool.execute("Python")
        
        assert "[Python 101 - Lesson 1]" in result
        assert len(self.search_tool.last_sources) == 1
        assert self.search_tool.last_sources[0]["url"] is None
    
    def test_get_tool_definition(self):
        """Test tool definition structure"""
        definition = self.search_tool.get_tool_definition()
        
        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["type"] == "object"
        assert "query" in definition["input_schema"]["properties"]
        assert "course_name" in definition["input_schema"]["properties"]
        assert "lesson_number" in definition["input_schema"]["properties"]
        assert definition["input_schema"]["required"] == ["query"]


class TestCourseOutlineTool:
    """Test the CourseOutlineTool functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_vector_store = Mock()
        self.outline_tool = CourseOutlineTool(self.mock_vector_store)
    
    def test_execute_successful_outline(self):
        """Test successful course outline retrieval"""
        # Mock course name resolution
        self.mock_vector_store._resolve_course_name.return_value = "Python Programming"
        
        # Mock course catalog response
        mock_catalog_response = {
            "metadatas": [{
                "title": "Python Programming",
                "instructor": "John Doe",
                "course_link": "https://example.com/python-course",
                "lessons_json": '[{"lesson_number": 1, "lesson_title": "Introduction"}, {"lesson_number": 2, "lesson_title": "Variables"}]'
            }]
        }
        self.mock_vector_store.course_catalog.get.return_value = mock_catalog_response
        
        result = self.outline_tool.execute("Python")
        
        # Verify course name was resolved
        self.mock_vector_store._resolve_course_name.assert_called_once_with("Python")
        
        # Verify catalog was queried
        self.mock_vector_store.course_catalog.get.assert_called_once_with(ids=["Python Programming"])
        
        # Verify formatted output
        assert "**Course:** Python Programming" in result
        assert "**Course Link:** https://example.com/python-course" in result
        assert "**Instructor:** John Doe" in result
        assert "- Lesson 1: Introduction" in result
        assert "- Lesson 2: Variables" in result
    
    def test_execute_course_not_found(self):
        """Test handling when course is not found"""
        self.mock_vector_store._resolve_course_name.return_value = None
        
        result = self.outline_tool.execute("Nonexistent Course")
        
        assert result == "No course found matching 'Nonexistent Course'"
    
    def test_execute_metadata_error(self):
        """Test handling of metadata retrieval errors"""
        self.mock_vector_store._resolve_course_name.return_value = "Python Programming"
        self.mock_vector_store.course_catalog.get.side_effect = Exception("Database error")
        
        result = self.outline_tool.execute("Python")
        
        assert "Error retrieving course outline: Database error" in result


class TestToolManager:
    """Test the ToolManager functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.tool_manager = ToolManager()
        self.mock_tool = Mock()
        self.mock_tool.get_tool_definition.return_value = {"name": "test_tool"}
        self.mock_tool.execute.return_value = "test result"
    
    def test_register_tool(self):
        """Test tool registration"""
        self.tool_manager.register_tool(self.mock_tool)
        
        assert "test_tool" in self.tool_manager.tools
        assert self.tool_manager.tools["test_tool"] == self.mock_tool
    
    def test_register_tool_no_name(self):
        """Test error when tool has no name"""
        self.mock_tool.get_tool_definition.return_value = {}
        
        with pytest.raises(ValueError, match="Tool must have a 'name' in its definition"):
            self.tool_manager.register_tool(self.mock_tool)
    
    def test_get_tool_definitions(self):
        """Test getting all tool definitions"""
        self.tool_manager.register_tool(self.mock_tool)
        
        definitions = self.tool_manager.get_tool_definitions()
        
        assert len(definitions) == 1
        assert definitions[0] == {"name": "test_tool"}
    
    def test_execute_tool(self):
        """Test tool execution"""
        self.tool_manager.register_tool(self.mock_tool)
        
        result = self.tool_manager.execute_tool("test_tool", param="value")
        
        self.mock_tool.execute.assert_called_once_with(param="value")
        assert result == "test result"
    
    def test_execute_nonexistent_tool(self):
        """Test execution of non-existent tool"""
        result = self.tool_manager.execute_tool("nonexistent", param="value")
        
        assert result == "Tool 'nonexistent' not found"
    
    def test_get_last_sources(self):
        """Test source tracking"""
        # Create mock tool with sources
        tool_with_sources = Mock()
        tool_with_sources.get_tool_definition.return_value = {"name": "source_tool"}
        tool_with_sources.last_sources = [{"text": "source1", "url": None}]
        
        self.tool_manager.register_tool(tool_with_sources)
        
        sources = self.tool_manager.get_last_sources()
        
        assert len(sources) == 1
        assert sources[0]["text"] == "source1"
    
    def test_reset_sources(self):
        """Test source resetting"""
        # Create mock tool with sources
        tool_with_sources = Mock()
        tool_with_sources.get_tool_definition.return_value = {"name": "source_tool"}
        tool_with_sources.last_sources = [{"text": "source1", "url": None}]
        
        self.tool_manager.register_tool(tool_with_sources)
        
        self.tool_manager.reset_sources()
        
        assert tool_with_sources.last_sources == []


if __name__ == "__main__":
    pytest.main([__file__])