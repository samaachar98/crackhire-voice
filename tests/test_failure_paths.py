import asyncio
from app.providers.whisper import WhisperProvider
from app.providers.minimax import MiniMaxProvider

async def run_test():
    whisper = WhisperProvider()
    minimax = MiniMaxProvider()
    # missing keys paths should fail soft, not crash
    try:
        _ = await whisper.transcribe(b'')
        _ = await minimax.respond('hi', [])
        print('FAILURE_PATHS_SOFT_OK')
    except Exception as e:
        raise RuntimeError(f'failure path crashed: {e}')

asyncio.run(run_test())
