import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.orchestration.voice_pipeline import VoicePipeline

app = FastAPI(title='CrackHire Voice Bot')

@app.get('/health')
async def health():
    return JSONResponse({
        'status': 'healthy',
        'services': {
            'stt': bool(settings.openai_api_key),
            'llm': bool(settings.minimax_api_key or settings.groq_api_key),
            'tts': True,
        },
        'config': {
            'stt': 'whisper',
            'llm_model': settings.minimax_model,
            'tts': 'piper',
            'tts_voice': settings.piper_voice,
        }
    })

@app.websocket('/ws/interview/{interview_id}')
async def websocket_endpoint(websocket: WebSocket, interview_id: str):
    await websocket.accept()
    pipeline = VoicePipeline()
    audio_buffer = b''
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('type')
            if msg_type == 'audio':
                audio_buffer += base64.b64decode(data.get('data', ''))
            elif msg_type == 'stop' and audio_buffer:
                result = await pipeline.run_once(audio_buffer)
                await websocket.send_json({'type': 'transcript', 'text': result['transcript']})
                await websocket.send_json({'type': 'response', 'text': result['response'], 'metrics': result['metrics']})
                if result['audio']:
                    await websocket.send_json({'type': 'audio', 'data': base64.b64encode(result['audio']).decode(), 'format': 'wav'})
                audio_buffer = b''
            elif msg_type == 'interrupt':
                audio_buffer = b''
                await websocket.send_json({'type': 'interrupt', 'status': 'stopped'})
    except WebSocketDisconnect:
        return
