# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Development
```bash
# Install dependencies
uv sync

# Start the application (quick start)
chmod +x run.sh && ./run.sh

# Start manually
cd backend && uv run uvicorn app:app --reload --port 8000

# Access points
# Web Interface: http://localhost:8000
# API Documentation: http://localhost:8000/docs
```

### Environment Setup
```bash
# Required .env file in root directory:
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## Architecture Overview

This is a **Retrieval-Augmented Generation (RAG) system** that enables semantic search and AI-powered responses over course materials.

### Core Architecture Pattern
The system uses a **tool-based AI architecture** where Claude decides whether to search the knowledge base or answer directly:

1. **RAG System** (`rag_system.py`) - Main orchestrator that coordinates all components
2. **AI Generator** (`ai_generator.py`) - Manages Claude API interactions with tool calling
3. **Search Tools** (`search_tools.py`) - Implements searchable tools that Claude can invoke
4. **Vector Store** (`vector_store.py`) - ChromaDB-based semantic search with embeddings
5. **Document Processor** (`document_processor.py`) - Parses structured course documents into searchable chunks

### Request Flow Architecture
```
User Query → FastAPI → RAG System → AI Generator → Claude API
                                      ↓ (tool decision)
                                   Search Tool → Vector Store → ChromaDB
                                      ↓
                                   Formatted Results → Second Claude API Call → Response
```

### Key Design Patterns

**Tool-Based Search**: Claude autonomously decides when to search vs answer directly. The `CourseSearchTool` is registered with the `ToolManager` and exposed to Claude through Anthropic's tool calling API.

**Session Management**: Conversation context maintained through `SessionManager` with configurable history limits.

**Structured Document Processing**: Course documents must follow this format:
```
Course Title: [title]
Course Link: [url] 
Course Instructor: [name]

Lesson 0: Introduction
Lesson Link: [url]
[lesson content]

Lesson 1: Next Topic
[lesson content]
```

**Chunk-Based Storage**: Documents are split into overlapping chunks with lesson context preserved. Each chunk stores course title, lesson number, and position for traceability.

### Configuration System
All settings centralized in `config.py` using dataclass pattern:
- Anthropic model: `claude-sonnet-4-20250514`
- Embedding model: `all-MiniLM-L6-v2` 
- Chunk size: 800 chars with 100 char overlap
- ChromaDB path: `./chroma_db`

### Data Models
Core entities defined in `models.py`:
- `Course`: Container with lessons and metadata
- `Lesson`: Individual lesson with number and title  
- `CourseChunk`: Text chunk with full traceability metadata

### Document Storage Strategy
Documents placed in `docs/` folder are automatically processed on startup. The system:
- Parses structured course format
- Creates semantic embeddings using sentence-transformers
- Stores in ChromaDB with rich metadata for filtering
- Avoids reprocessing existing courses

### Frontend Integration
Single-page application in `frontend/` with:
- Real-time chat interface with loading states
- Markdown rendering for AI responses
- Collapsible source citations
- Course statistics sidebar

### Error Handling Strategy
Each component has error boundaries:
- Document parsing falls back to whole-document chunks
- Vector search returns empty results gracefully  
- AI generation handles tool execution failures
- Frontend shows user-friendly error messages

## Development Notes

### Adding New Tools
1. Extend `Tool` abstract base class in `search_tools.py`
2. Implement `get_tool_definition()` and `execute()` methods
3. Register with `ToolManager` in `rag_system.py`
4. Claude will automatically discover and use the tool

### Document Format Requirements
Course documents must start with metadata lines and use "Lesson X:" markers for proper parsing. Malformed documents will be processed as single chunks.

### Vector Store Collections
ChromaDB uses separate collections for course metadata and content chunks, enabling both semantic search and structured filtering.

### Session Lifecycle
Sessions are ephemeral (in-memory only) and automatically created on first query. History is limited by `MAX_HISTORY` configuration.
- Always use uv to run the server. Do not use pip directly.
- Make sure to use uv to manage all dependencies.
- use uv to run Python files.