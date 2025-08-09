# Query Processing Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  FRONTEND                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  User Input → sendMessage() → POST /api/query                                  │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────────────┐ │
│  │ Chat Interface  │    │ Loading Message  │    │ Request Body:               │ │
│  │ - Input Field   │───▶│ - Disable Input  │───▶│ {                           │ │
│  │ - Send Button   │    │ - Show Spinner   │    │   "query": "user question", │ │
│  └─────────────────┘    └──────────────────┘    │   "session_id": "optional"  │ │
│                                                 │ }                           │ │
│                                                 └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ HTTP POST
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI BACKEND                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  app.py: /api/query endpoint                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. Receive QueryRequest                                                     │ │
│  │ 2. Create session if needed                                                 │ │
│  │ 3. Call rag_system.query(query, session_id)                                │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               RAG SYSTEM                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  rag_system.py: Main orchestrator                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. Format prompt: "Answer this question about course materials: {query}"   │ │
│  │ 2. Get conversation history from session_manager                           │ │
│  │ 3. Call ai_generator.generate_response() with tools                        │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AI GENERATOR                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ai_generator.py: Claude API interaction                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. Build system prompt + conversation context                              │ │
│  │ 2. First Anthropic API call with tools enabled                             │ │
│  │ 3. Claude decides: Direct answer OR Tool use                               │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────▼─────────────────┐
                    │                                   │
                    ▼                                   ▼
        ┌─────────────────┐                ┌─────────────────────┐
        │ Direct Answer   │                │ Tool Use Required   │
        │                 │                │                     │
        │ Return response │                │ Execute search tool │
        └─────────────────┘                └─────────────────────┘
                    │                                   │
                    │                                   ▼
                    │               ┌─────────────────────────────────────────────┐
                    │               │              TOOL EXECUTION                 │
                    │               ├─────────────────────────────────────────────┤
                    │               │  search_tools.py: CourseSearchTool          │
                    │               │  ┌─────────────────────────────────────────┐ │
                    │               │  │ 1. Extract tool parameters from Claude │ │
                    │               │  │ 2. Call vector_store.search()          │ │
                    │               │  │ 3. Format results with context         │ │
                    │               │  │ 4. Track sources for UI                │ │
                    │               │  └─────────────────────────────────────────┘ │
                    │               └─────────────────────────────────────────────┘
                    │                                   │
                    │                                   ▼
                    │               ┌─────────────────────────────────────────────┐
                    │               │              VECTOR STORE                   │
                    │               ├─────────────────────────────────────────────┤
                    │               │  vector_store.py: ChromaDB search           │
                    │               │  ┌─────────────────────────────────────────┐ │
                    │               │  │ 1. Semantic similarity search          │ │
                    │               │  │ 2. Apply course/lesson filters         │ │
                    │               │  │ 3. Return relevant chunks + metadata   │ │
                    │               │  └─────────────────────────────────────────┘ │
                    │               └─────────────────────────────────────────────┘
                    │                                   │
                    │                                   ▼
                    │               ┌─────────────────────────────────────────────┐
                    │               │           FINAL AI RESPONSE                 │
                    │               ├─────────────────────────────────────────────┤
                    │               │  ai_generator.py: Second API call           │
                    │               │  ┌─────────────────────────────────────────┐ │
                    │               │  │ 1. Add tool results to conversation    │ │
                    │               │  │ 2. Second Anthropic API call           │ │
                    │               │  │ 3. Synthesize search results           │ │
                    │               │  │ 4. Generate final answer               │ │
                    │               │  └─────────────────────────────────────────┘ │
                    │               └─────────────────────────────────────────────┘
                    │                                   │
                    └───────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            RESPONSE ASSEMBLY                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  rag_system.py: Final processing                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. Get sources from tool_manager.get_last_sources()                        │ │
│  │ 2. Update conversation history                                              │ │
│  │ 3. Return tuple: (response, sources)                                       │ │
│  │ 4. Reset sources in tool_manager                                           │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ JSON Response
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND RESPONSE                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  script.js: Response handling                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ Response: { "answer": "...", "sources": [...], "session_id": "..." }       │ │
│  │                                                                             │ │
│  │ 1. Remove loading message                                                   │ │
│  │ 2. Parse markdown in response                                               │ │
│  │ 3. Display answer with sources in collapsible section                      │ │
│  │ 4. Store session_id for future queries                                     │ │
│  │ 5. Re-enable input for next query                                          │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  KEY FEATURES                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│ • Session Management: Maintains conversation context across queries            │
│ • Tool-based Architecture: Claude decides when to search vs direct answer      │
│ • Semantic Search: ChromaDB embeddings for content similarity matching        │
│ • Source Tracking: Full traceability from answer back to course documents     │
│ • Error Handling: Graceful fallbacks at each layer                            │
│ • Real-time UI: Loading states and markdown rendering                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Flow Summary

1. **User Input** → Frontend captures query and sends POST request
2. **API Gateway** → FastAPI routes to RAG system  
3. **RAG Orchestration** → Manages session, calls AI generator
4. **AI Decision** → Claude decides whether to search or answer directly
5. **Tool Execution** → If needed, searches vector store for relevant content
6. **Vector Search** → ChromaDB finds semantically similar document chunks
7. **Response Synthesis** → Claude combines search results into final answer
8. **Source Tracking** → System maintains traceability to original documents
9. **Frontend Display** → Renders markdown response with collapsible sources

The architecture enables intelligent, context-aware responses while maintaining full transparency about information sources.