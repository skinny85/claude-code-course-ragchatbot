from typing import Any, Dict, List, Optional

import anthropic


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Maximum number of sequential tool calling rounds
    MAX_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search and outline tools for course information.

Tool Usage:
- Use the **search_course_content** tool for questions about specific course content or detailed educational materials
- Use the **get_course_outline** tool for questions about course structure, lesson lists, or course overviews
- **Sequential tool usage**: For complex queries, you can make multiple tool calls across separate reasoning rounds (maximum 2 rounds)
- Synthesize tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives

Tool Selection Guidelines:
- **Course outline queries**: Use get_course_outline for questions about what lessons are in a course, course structure, or course overview
- **Content-specific queries**: Use search_course_content for detailed questions about specific topics or materials
- **Complex multi-part queries**: Use tools sequentially when you need to:
  - Compare information from different courses or lessons
  - Search for one thing, then use those results to search for something else
  - Get course structure first, then search for specific content within lessons
- **General knowledge questions**: Answer using existing knowledge without tools

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course outline questions**: Use get_course_outline tool to provide complete course information including course title, course link, and all lessons with numbers and titles
- **Course-specific content questions**: Use search_course_content tool first, then answer
- **Complex queries**: Use tools sequentially as needed, reasoning about results between calls
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the course outline"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to MAX_ROUNDS sequential tool calls for complex queries.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize conversation state for multi-round processing
        messages = [{"role": "user", "content": query}]
        current_round = 1

        # Multi-round controller loop
        while True:
            # Prepare API call parameters
            api_params = {
                **self.base_params,
                "messages": messages.copy(),
                "system": system_content,
            }

            # Add tools only if we haven't exceeded max tool rounds
            if tools and current_round <= self.MAX_ROUNDS:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            # Get response from Claude
            try:
                response = self.client.messages.create(**api_params)
            except Exception as e:
                # Handle API errors gracefully
                if current_round == 1:
                    raise e  # Re-raise on first round failure
                else:
                    # Return partial response from previous rounds if available
                    return "I encountered an error while processing your request. Please try again."

            # Check if Claude wants to use tools and we haven't exceeded max rounds
            if (
                response.stop_reason == "tool_use"
                and tool_manager
                and current_round <= self.MAX_ROUNDS
            ):
                # Execute tools and get updated messages
                try:
                    updated_messages, tool_success = self._handle_tool_execution(
                        response, messages, tool_manager
                    )

                    if not tool_success:
                        # Tool execution failed - return response with error message
                        return "I encountered an issue while searching for information."

                    # Update messages with tool results for next round
                    messages = updated_messages
                    current_round += 1

                    # Continue to next round if we haven't exceeded max rounds
                    continue

                except Exception as e:
                    # Handle tool execution errors gracefully
                    return "I encountered an issue while processing your request."

            else:
                # No tool use, max rounds reached, or no tool manager - return final response
                if response.stop_reason == "tool_use" and not tool_manager:
                    # Claude wants to use tools but no tool manager available
                    return "I need to search for information to answer your question, but search functionality is not available."
                else:
                    # Normal text response
                    return response.content[0].text

    def _handle_tool_execution(
        self, initial_response, current_messages: List, tool_manager
    ):
        """
        Handle execution of tool calls and return updated messages for continuation.

        Args:
            initial_response: The response containing tool use requests
            current_messages: Current conversation messages
            tool_manager: Manager to execute tools

        Returns:
            Tuple of (updated_messages, success_flag) for next round
        """
        # Start with existing messages
        messages = current_messages.copy()

        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})

        # Execute all tool calls and collect results
        tool_results = []
        execution_success = True

        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                try:
                    tool_result = tool_manager.execute_tool(
                        content_block.name, **content_block.input
                    )

                    # Handle case where tool returns None or empty result
                    if tool_result is None:
                        tool_result = "No results found."

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": str(tool_result),
                        }
                    )

                except Exception as e:
                    # Tool execution failed - mark as unsuccessful
                    execution_success = False
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": f"Tool execution failed: {str(e)}",
                        }
                    )

        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        return messages, execution_success
