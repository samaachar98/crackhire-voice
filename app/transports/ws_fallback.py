import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.pipecat.runtime import PipecatRuntimeBootstrap
from app.pipecat.events import make_event

router = APIRouter(prefix='/ws-fallback', tags=['ws-fallback'])
runtime = PipecatRuntimeBootstrap()

@router.websocket('/interview/{session_id}')
async def ws_fallback(websocket: WebSocket, session_id: str):
    await websocket.accept()
    interrupt = None
    audio_buffer = bytearray()
    turn_id = 0
    try:
        import asyncio
        interrupt = asyncio.Event()
        while True:
            data = await websocket.receive_json()
            kind = data.get('type')
            if kind == 'audio':
                audio_buffer.extend(base64.b64decode(data.get('data', '')))
            elif kind == 'stop' and audio_buffer:
                turn_id += 1
                result = await runtime.run_turn(session_id, runtime.normalize_ingress_audio(bytes(audio_buffer)), interrupt)
                events = []
                if result.get('cancelled'):
                    events.append(make_event('turn.interrupted', session_id, turn_id, {'stage': result.get('stage')}))
                else:
                    events.append(make_event('transcript.final', session_id, turn_id, {'text': result.get('transcript')}))
                    events.append(make_event('response.text', session_id, turn_id, {'text': result.get('response')}))
                    events.append(make_event('audio.ready', session_id, turn_id, {'has_audio': bool(result.get('audio'))}))
                    events.append(make_event('metrics.turn', session_id, turn_id, result.get('metrics', {})))
                await websocket.send_json({'ok': True, 'session_id': session_id, 'turn_id': turn_id, 'events': events})
                audio_buffer.clear()
            elif kind == 'interrupt' and interrupt is not None:
                interrupt.set()
                await websocket.send_json({'ok': True, 'session_id': session_id, 'events': [make_event('turn.interrupted', session_id, turn_id, {'stage': 'transport_interrupt'})]})
    except WebSocketDisconnect:
        runtime.remove_session(session_id)
        return
