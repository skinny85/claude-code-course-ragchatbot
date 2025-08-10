import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ai_generator import AIGenerator


class MockAnthropicResponse:
    """Mock Anthropic API response"""

    def __init__(self, content_text=None, stop_reason="end_turn", tool_calls=None):
        self.stop_reason = stop_reason
        if tool_calls:
            self.content = tool_calls
        else:
            mock_content = Mock()
            mock_content.text = content_text or "Test response"
            self.content = [mock_content]


class MockToolUseContent:
    """Mock tool use content block"""

    def __init__(
        self, tool_id="test_id", name="search_course_content", input_data=None
    ):
        self.type = "tool_use"
        self.id = tool_id
        self.name = name
        self.input = input_data or {"query": "test query"}


class TestAIGenerator:
    """Test AIGenerator functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.api_key = "test-api-key"
        self.model = "claude-sonnet-4-20250514"
        self.ai_generator = AIGenerator(self.api_key, self.model)

    @patch("ai_generator.anthropic.Anthropic")
    def test_init(self, mock_anthropic_class):
        """Test AIGenerator initialization"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        ai_gen = AIGenerator("test-key", "test-model")

        mock_anthropic_class.assert_called_once_with(api_key="test-key")
        assert ai_gen.model == "test-model"
        assert ai_gen.client == mock_client
        assert ai_gen.base_params["model"] == "test-model"
        assert ai_gen.base_params["temperature"] == 0
        assert ai_gen.base_params["max_tokens"] == 800

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_no_tools(self, mock_anthropic_class):
        """Test generating response without tools"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MockAnthropicResponse("Direct answer without tools")
        mock_client.messages.create.return_value = mock_response

        ai_gen = AIGenerator("test-key", "test-model")
        result = ai_gen.generate_response("What is Python?")

        # Verify API call
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args[1]

        assert call_args["model"] == "test-model"
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "What is Python?"
        assert "tools" not in call_args

        assert result == "Direct answer without tools"

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_conversation_history(self, mock_anthropic_class):
        """Test generating response with conversation history"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MockAnthropicResponse("Response with history")
        mock_client.messages.create.return_value = mock_response

        ai_gen = AIGenerator("test-key", "test-model")
        history = "Previous conversation context"

        result = ai_gen.generate_response(
            "Follow up question", conversation_history=history
        )

        call_args = mock_client.messages.create.call_args[1]
        assert history in call_args["system"]
        assert result == "Response with history"

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_tools_no_tool_use(self, mock_anthropic_class):
        """Test generating response with tools available but not used"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MockAnthropicResponse("Direct answer, no tool needed")
        mock_client.messages.create.return_value = mock_response

        ai_gen = AIGenerator("test-key", "test-model")
        tools = [{"name": "search_tool", "description": "Search tool"}]

        result = ai_gen.generate_response("General question", tools=tools)

        call_args = mock_client.messages.create.call_args[1]
        assert call_args["tools"] == tools
        assert call_args["tool_choice"] == {"type": "auto"}
        assert result == "Direct answer, no tool needed"

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_tool_use(self, mock_anthropic_class):
        """Test generating response with single tool use (backward compatibility)"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock initial response with tool use
        tool_use_content = MockToolUseContent()
        initial_response = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool_use_content]
        )

        # Mock final response after tool execution (no more tools)
        final_response = MockAnthropicResponse("Final answer based on tool results")

        # Setup mock to return different responses for different calls
        mock_client.messages.create.side_effect = [initial_response, final_response]

        ai_gen = AIGenerator("test-key", "test-model")
        tools = [{"name": "search_course_content", "description": "Search tool"}]

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool execution result"

        result = ai_gen.generate_response(
            "Search for Python content", tools=tools, tool_manager=mock_tool_manager
        )

        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="test query"
        )

        # Verify two API calls were made (tool call round + final response)
        assert mock_client.messages.create.call_count == 2

        # Verify final result
        assert result == "Final answer based on tool results"

    @patch("ai_generator.anthropic.Anthropic")
    def test_handle_tool_execution_single_tool(self, mock_anthropic_class):
        """Test tool execution handling with single tool"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        ai_gen = AIGenerator("test-key", "test-model")

        # Create mock initial response
        tool_content = MockToolUseContent(
            "tool_id_1", "search_tool", {"query": "Python"}
        )
        initial_response = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool_content]
        )

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results for Python"

        current_messages = [{"role": "user", "content": "Find Python content"}]

        updated_messages, success = ai_gen._handle_tool_execution(
            initial_response, current_messages, mock_tool_manager
        )

        # Verify tool execution
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_tool", query="Python"
        )

        # Verify success flag
        assert success is True

        # Verify message structure
        assert len(updated_messages) == 3  # original + assistant + tool_result

        # Check tool result message structure
        tool_result_message = updated_messages[2]
        assert tool_result_message["role"] == "user"
        assert len(tool_result_message["content"]) == 1
        assert tool_result_message["content"][0]["type"] == "tool_result"
        assert tool_result_message["content"][0]["tool_use_id"] == "tool_id_1"
        assert (
            tool_result_message["content"][0]["content"] == "Search results for Python"
        )

        # Check assistant message
        assert updated_messages[1]["role"] == "assistant"
        assert updated_messages[1]["content"] == [tool_content]

    @patch("ai_generator.anthropic.Anthropic")
    def test_handle_tool_execution_multiple_tools(self, mock_anthropic_class):
        """Test tool execution handling with multiple tools"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        ai_gen = AIGenerator("test-key", "test-model")

        # Create mock initial response with multiple tool uses
        tool1 = MockToolUseContent("tool_id_1", "search_tool", {"query": "Python"})
        tool2 = MockToolUseContent(
            "tool_id_2", "outline_tool", {"course_name": "Python"}
        )

        initial_response = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool1, tool2]
        )

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Search results",
            "Course outline",
        ]

        current_messages = [{"role": "user", "content": "Find Python info"}]

        updated_messages, success = ai_gen._handle_tool_execution(
            initial_response, current_messages, mock_tool_manager
        )

        # Verify both tools were executed
        assert mock_tool_manager.execute_tool.call_count == 2
        mock_tool_manager.execute_tool.assert_any_call("search_tool", query="Python")
        mock_tool_manager.execute_tool.assert_any_call(
            "outline_tool", course_name="Python"
        )

        # Verify success flag
        assert success is True

        # Verify tool results message contains both results
        tool_result_message = updated_messages[2]
        assert len(tool_result_message["content"]) == 2

        # Check both tool results
        tool_results = tool_result_message["content"]
        assert tool_results[0]["tool_use_id"] == "tool_id_1"
        assert tool_results[0]["content"] == "Search results"
        assert tool_results[1]["tool_use_id"] == "tool_id_2"
        assert tool_results[1]["content"] == "Course outline"

    @patch("ai_generator.anthropic.Anthropic")
    def test_tool_execution_with_no_tool_manager(self, mock_anthropic_class):
        """Test tool execution when no tool manager is provided"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_use_content = MockToolUseContent()
        response_with_tools = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool_use_content]
        )
        mock_client.messages.create.return_value = response_with_tools

        ai_gen = AIGenerator("test-key", "test-model")
        tools = [{"name": "search_tool"}]

        # With no tool manager, the system should return a fallback response
        result = ai_gen.generate_response("Query", tools=tools, tool_manager=None)

        # Should return some meaningful response when tool manager is unavailable
        assert isinstance(result, str) and len(result) > 0

    def test_system_prompt_content(self):
        """Test that system prompt contains expected instructions"""
        assert "search_course_content" in AIGenerator.SYSTEM_PROMPT
        assert "get_course_outline" in AIGenerator.SYSTEM_PROMPT
        assert "tool" in AIGenerator.SYSTEM_PROMPT.lower()
        assert "course" in AIGenerator.SYSTEM_PROMPT.lower()

    @patch("ai_generator.anthropic.Anthropic")
    def test_api_error_handling(self, mock_anthropic_class):
        """Test handling of Anthropic API errors"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock API to raise an exception
        mock_client.messages.create.side_effect = Exception("API Error")

        ai_gen = AIGenerator("test-key", "test-model")

        # Should propagate the exception
        with pytest.raises(Exception, match="API Error"):
            ai_gen.generate_response("Test query")

    @patch("ai_generator.anthropic.Anthropic")
    def test_sequential_tool_calling_two_rounds(self, mock_anthropic_class):
        """Test sequential tool calling with 2 rounds"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Round 1: Get course outline
        tool1_content = MockToolUseContent(
            "tool_id_1", "get_course_outline", {"course_name": "Python Basics"}
        )
        round1_response = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool1_content]
        )

        # Round 2: Search for specific content based on outline
        tool2_content = MockToolUseContent(
            "tool_id_2", "search_course_content", {"query": "lesson 4 content"}
        )
        round2_response = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool2_content]
        )

        # Final response after 2 rounds
        final_response = MockAnthropicResponse(
            "Here's the comparison between the courses"
        )

        # Setup responses for 3 API calls
        mock_client.messages.create.side_effect = [
            round1_response,
            round2_response,
            final_response,
        ]

        ai_gen = AIGenerator("test-key", "test-model")
        tools = [{"name": "get_course_outline"}, {"name": "search_course_content"}]

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Course outline: Lesson 1: Intro, Lesson 2: Variables, Lesson 3: Functions, Lesson 4: Classes",
            "Lesson 4 covers object-oriented programming concepts",
        ]

        result = ai_gen.generate_response(
            "Compare lesson 4 of Python Basics with similar content",
            tools=tools,
            tool_manager=mock_tool_manager,
        )

        # Verify 3 API calls made (2 tool rounds + final)
        assert mock_client.messages.create.call_count == 3

        # Verify both tools executed
        assert mock_tool_manager.execute_tool.call_count == 2
        mock_tool_manager.execute_tool.assert_any_call(
            "get_course_outline", course_name="Python Basics"
        )
        mock_tool_manager.execute_tool.assert_any_call(
            "search_course_content", query="lesson 4 content"
        )

        assert result == "Here's the comparison between the courses"

    @patch("ai_generator.anthropic.Anthropic")
    def test_max_rounds_enforcement(self, mock_anthropic_class):
        """Test that MAX_ROUNDS (2) is enforced"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # All 3 responses want to use tools (should stop after 2)
        tool_content = MockToolUseContent("tool_id", "search_tool", {"query": "test"})
        tool_response = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool_content]
        )

        # Final response after max rounds reached
        final_response = MockAnthropicResponse("Final answer after max rounds")

        # Setup responses - 3rd call should return final response
        mock_client.messages.create.side_effect = [
            tool_response,
            tool_response,
            final_response,
        ]

        ai_gen = AIGenerator("test-key", "test-model")
        tools = [{"name": "search_tool"}]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        result = ai_gen.generate_response(
            "Complex query requiring multiple searches",
            tools=tools,
            tool_manager=mock_tool_manager,
        )

        # Should make exactly 3 API calls (2 tool rounds + final without tools)
        assert mock_client.messages.create.call_count == 3

        # Tools should be executed exactly 2 times (max rounds)
        assert mock_tool_manager.execute_tool.call_count == 2

        assert result == "Final answer after max rounds"

    @patch("ai_generator.anthropic.Anthropic")
    def test_early_termination_no_tools_needed(self, mock_anthropic_class):
        """Test early termination when Claude doesn't need tools"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First response doesn't use tools - should terminate immediately
        direct_response = MockAnthropicResponse(
            "I can answer this directly without searching"
        )
        mock_client.messages.create.return_value = direct_response

        ai_gen = AIGenerator("test-key", "test-model")
        tools = [{"name": "search_tool"}]
        mock_tool_manager = Mock()

        result = ai_gen.generate_response(
            "What is Python?", tools=tools, tool_manager=mock_tool_manager
        )

        # Should make only 1 API call
        assert mock_client.messages.create.call_count == 1

        # No tools should be executed
        assert mock_tool_manager.execute_tool.call_count == 0

        assert result == "I can answer this directly without searching"

    @patch("ai_generator.anthropic.Anthropic")
    def test_tool_execution_failure_handling(self, mock_anthropic_class):
        """Test graceful handling of tool execution failures"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_content = MockToolUseContent("tool_id", "search_tool", {"query": "test"})
        tool_response = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool_content]
        )

        mock_client.messages.create.return_value = tool_response

        ai_gen = AIGenerator("test-key", "test-model")
        tools = [{"name": "search_tool"}]

        # Mock tool manager to raise exception
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = Exception("Tool failed")

        result = ai_gen.generate_response(
            "Search for something", tools=tools, tool_manager=mock_tool_manager
        )

        # Should handle the error gracefully and return a fallback response
        assert "encountered an issue" in result.lower() or len(result) > 0
        assert mock_client.messages.create.call_count == 1
        assert mock_tool_manager.execute_tool.call_count == 1

    @patch("ai_generator.anthropic.Anthropic")
    def test_tool_execution_returns_none_handling(self, mock_anthropic_class):
        """Test handling when tool returns None"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        ai_gen = AIGenerator("test-key", "test-model")

        tool_content = MockToolUseContent("tool_id", "search_tool", {"query": "test"})
        initial_response = MockAnthropicResponse(
            stop_reason="tool_use", tool_calls=[tool_content]
        )

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = None

        current_messages = [{"role": "user", "content": "Test query"}]

        updated_messages, success = ai_gen._handle_tool_execution(
            initial_response, current_messages, mock_tool_manager
        )

        # Should handle None return and convert to "No results found."
        assert success is True
        tool_result = updated_messages[2]["content"][0]
        assert tool_result["content"] == "No results found."

    def test_max_rounds_constant(self):
        """Test that MAX_ROUNDS constant is set correctly"""
        assert AIGenerator.MAX_ROUNDS == 2


if __name__ == "__main__":
    pytest.main([__file__])
