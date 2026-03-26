import aiohttp
from app.core.config import settings

class WhisperProvider:
    async def transcribe(self, audio_bytes: bytes) -> str:
        if not settings.openai_api_key:
            return ""
        data = aiohttp.FormData()
        data.add_field('file', audio_bytes, filename='audio.wav', content_type='audio/wav')
        data.add_field('model', 'whisper-1')
        data.add_field('language', 'en')
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.openai.com/v1/audio/transcriptions',
                data=data,
                headers={'Authorization': f'Bearer {settings.openai_api_key}'}
            ) as resp:
                if resp.status != 200:
                    return ""
                payload = await resp.json()
                return payload.get('text', '')
