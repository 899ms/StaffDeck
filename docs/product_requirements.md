# Skill Agent Loop MVP Requirements

This repository implements the first version of a general enterprise Skill Agent Loop service.

## MVP Flow

1. Enterprise configures an OpenAI-compatible model.
2. Enterprise creates, edits, distills, publishes, or archives Skill Cards.
3. Enterprise registers HTTP API tools.
4. End user starts a chat session and sends natural-language requests.
5. Backend routes the request to a skill, advances state, calls tools when needed, and replies.
6. Enterprise reviews Router decisions, Step Agent output, tool calls, messages, and session state in Trace.

## Explicit Non-Goals

- MCP integration
- RAG pipeline
- BPMN or complex state-machine compiler
- Multi-agent orchestration
- Full authentication and authorization
- Real high-risk transactions such as payments or refunds

## Demo Data

Startup seeds `tenant_demo`, a refund skill, an exchange skill, and the mock `order.query` HTTP tool. A default model config is seeded only when `DEMO_MODEL_API_KEY` is provided in the backend environment.
