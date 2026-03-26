from openai import AsyncOpenAI
from app.core.config import settings

class MiniMaxProvider:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.minimax_api_key, base_url='https://api.minimax.chat/v1')

    async def respond(self, text: str, messages: list[dict]) -> str:
        if not settings.minimax_api_key:
            return 'Missing MiniMax key.'
        resp = await self.client.chat.completions.create(
            model=settings.minimax_model,
            messages=messages + [{'role': 'user', 'content': text}],
            temperature=0.4,
            max_tokens=120,
        )
        return resp.choices[0].message.content or ''
