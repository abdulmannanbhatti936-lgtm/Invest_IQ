"""
MOCK provider for the Playwright run only (refused outside ENVIRONMENT=development, see
core/config.py). It never calls a model: it reads the grounding context out of the system
prompt and answers with a fixed sentence built from its figures, labelled "MOCK reply", so the
end-to-end test exercises the real endpoint, figure check and source tags.
"""

import json
import re

from integrations.llm.base import LLMResult, Provider

MOCK_MODEL = "MOCK-chat-v1"
_CONTEXT = re.compile(r"<context>(.*)</context>", re.DOTALL)


class MockProvider(Provider):
    name = "mock"
    model = MOCK_MODEL

    def complete(self, system, turns, *, max_tokens, temperature, deadline) -> LLMResult:
        context = json.loads(_CONTEXT.search(system).group(1))
        portfolio = context["portfolio"]
        if portfolio is None:
            text = (
                "MOCK reply: you do not have a portfolio yet. You can generate one on the "
                "Portfolio screen."
            )
        else:
            totals = portfolio["totals"]
            text = (
                f"MOCK reply: your portfolio cost {totals['total_cost']} and "
                f"{totals['cash_left']} was left as cash."
            )
        return LLMResult(text=text, model=MOCK_MODEL, input_tokens=None, output_tokens=None)
