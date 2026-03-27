import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.orchestration.voice_pipeline import VoicePipeline
from app.services.session_manager import SessionManager
from app.models.session import SessionState
from app.telemetry.metrics import metrics_store
from app.transports.webrtc import router as webrtc_router

app = FastAPI(title='CrackHire Voice Bot')
session_manager = SessionManager()

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
    session = session_manager.get_or_create(interview_id)
    audio_buffer = b''
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('type')
            if msg_type == 'audio':
                audio_buffer += base64.b64decode(data.get('data', ''))
            elif msg_type == 'stop' and audio_buffer:
                session_manager.set_state(interview_id, SessionState.PROCESSING)
                result = await pipeline.run_once(audio_buffer)
                await websocket.send_json({'type': 'transcript', 'text': result['transcript']})
                await websocket.send_json({'type': 'response', 'text': result['response'], 'metrics': result['metrics']})
                if result['audio']:
                    session_manager.set_state(interview_id, SessionState.SPEAKING)
                    await websocket.send_json({'type': 'audio', 'data': base64.b64encode(result['audio']).decode(), 'format': 'wav'})
                session_manager.set_state(interview_id, SessionState.LISTENING)
                audio_buffer = b''
            elif msg_type == 'interrupt':
                audio_buffer = b''
                session_manager.set_state(interview_id, SessionState.INTERRUPTED)
                await websocket.send_json({'type': 'interrupt', 'status': 'stopped'})
                session_manager.set_state(interview_id, SessionState.LISTENING)
    except WebSocketDisconnect:
        session_manager.remove(interview_id)
        return


app.include_router(webrtc_router)

@app.get('/ready')
async def ready():
    return {
        'status': 'ready' if (settings.openai_api_key and (settings.minimax_api_key or settings.groq_api_key) and settings.piper_voice_path) else 'partial',
        'providers': {
            'stt': bool(settings.openai_api_key),
            'llm': bool(settings.minimax_api_key or settings.groq_api_key),
            'tts': bool(settings.piper_voice_path),
        }
    }

@app.get('/metrics')
async def metrics():
    return {'status': 'ok', 'metrics': metrics_store.summary()}
