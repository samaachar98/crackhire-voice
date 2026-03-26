from __future__ import annotations

import asyncio
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack

from app.orchestration.voice_pipeline import VoicePipeline

router = APIRouter(prefix='/webrtc', tags=['webrtc'])
pcs: Dict[str, RTCPeerConnection] = {}
session_workers: Dict[str, asyncio.Task] = {}
session_buffers: Dict[str, bytearray] = {}
session_events: Dict[str, dict[str, Any]] = {}

class OfferRequest(BaseModel):
    sdp: str
    type: str
    session_id: str

async def audio_worker(session_id: str, track: MediaStreamTrack):
    buffer = session_buffers.setdefault(session_id, bytearray())
    pipeline = VoicePipeline()
    try:
        while True:
            frame = await track.recv()
            pcm = frame.to_ndarray().tobytes()
            buffer.extend(pcm)
            # naive turn threshold for milestone 1; real VAD later
            if len(buffer) > 32000 * 3:
                result = await pipeline.run_once(bytes(buffer))
                session_events[session_id] = {
                    'transcript': result['transcript'],
                    'response': result['response'],
                    'metrics': result['metrics'],
                    'audio_bytes': result['audio'],
                }
                buffer.clear()
    except Exception:
        return

@router.get('/health')
async def health():
    return {
        'status': 'ok',
        'transport': 'webrtc',
        'sessions': len(pcs),
        'workers': len(session_workers),
    }

@router.get('/session/{session_id}/events')
async def session_event(session_id: str):
    return {'ok': True, 'session_id': session_id, 'event': session_events.get(session_id)}

@router.post('/offer')
async def offer(body: OfferRequest):
    try:
        pc = RTCPeerConnection()
        pcs[body.session_id] = pc
        session_buffers[body.session_id] = bytearray()

        @pc.on('track')
        def on_track(track: MediaStreamTrack):
            if track.kind == 'audio':
                session_workers[body.session_id] = asyncio.create_task(audio_worker(body.session_id, track))

        @pc.on('connectionstatechange')
        async def on_connectionstatechange():
            if pc.connectionState in {'failed', 'closed', 'disconnected'}:
                worker = session_workers.pop(body.session_id, None)
                if worker:
                    worker.cancel()
                await pc.close()
                pcs.pop(body.session_id, None)
                session_buffers.pop(body.session_id, None)

        await pc.setRemoteDescription(RTCSessionDescription(sdp=body.sdp, type=body.type))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        return {
            'ok': True,
            'session_id': body.session_id,
            'sdp': pc.localDescription.sdp,
            'type': pc.localDescription.type,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'webrtc_offer_failed: {e}')
