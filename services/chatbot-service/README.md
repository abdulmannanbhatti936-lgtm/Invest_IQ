# chatbot-service

LLM orchestration and context grounding (Architecture.md §6.4, §12; PRD.md FR37-FR41). Built in
Phase 8.

Per Architecture.md §6.5 it runs as an internal module of `services/api`, not as a separate
network service:

- `services/api/services/chat_context.py` — the grounding context built from the database
- `services/api/services/chat_figure_check.py` — every number in a reply checked against it
- `services/api/services/chat_language.py` — Roman Urdu detection
- `services/api/services/chat_prompt.py` — the system prompt and fallback replies
- `services/api/services/chat_service.py` — one chat turn, limits and storage
- `services/api/integrations/llm/` — provider adapters (Gemini, Groq, Mistral, Claude, MOCK for tests)
- `services/api/routers/chat.py` — `POST /chat/message`, `GET` and `DELETE /chat/history`

Run the tests with `python -m pytest tests/test_chat_*.py tests/test_llm_providers.py` from
`services/api` (no model is called). The evaluation against a real model is
`python -m services.chat_eval` (needs `GEMINI_API_KEY` or `GROQ_API_KEY`; results in `docs/chat-eval/`).
