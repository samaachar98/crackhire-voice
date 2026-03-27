from __future__ import annotations

import asyncio
import time
import wave
import io
from fractions import Fraction
from typing import Dict, Any, Optional

import av
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.mediastreams import AudioStreamTrack

from app.audio.pcm import frame_to_mono_int16_bytes, resample_int16_mono, TARGET_SAMPLE_RATE
from app.audio.vad import SileroVAD
from app.orchestration.voice_pipeline import VoicePipeline

router = APIRouter(prefix='/webrtc', tags=['webrtc'])
pcs: Dict[str, RTCPeerConnection] = {}
session_workers: Dict[str, asyncio.Task] = {}
session_buffers: Dict[str, bytearray] = {}
session_events: Dict[str, dict[str, Any]] = {}
session_turns: Dict[str, int] = {}
session_last_audio_at: Dict[str, float] = {}
session_outbound_tracks: Dict[str, 'OutboundAudioTrack'] = {}
TURN_IDLE_SECONDS = 1.2
MIN_BUFFER_BYTES = 16000
vad = SileroVAD()

class OfferRequest(BaseModel):
    sdp: str
    type: str
    session_id: str

class OutboundAudioTrack(AudioStreamTrack):
    def __init__(self):
        super().__init__()
        self.queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.sample_rate = TARGET_SAMPLE_RATE
        self.samples_sent = 0
        self.speaking = False

    async def recv(self):
        pcm = await self.queue.get()
        if pcm is None:
            pcm = b"\x00\x00" * 320
            self.speaking = False
        else:
            self.speaking = True
        frame = av.AudioFrame(format='s16', layout='mono', samples=len(pcm) // 2)
        frame.sample_rate = self.sample_rate
        frame.planes[0].update(pcm)
        frame.pts = self.samples_sent
        frame.time_base = Fraction(1, self.sample_rate)
        self.samples_sent += frame.samples
        return frame

    async def push_wav_bytes(self, wav_bytes: bytes):
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wav:
            frames = wav.readframes(wav.getnframes())
            src_rate = wav.getframerate()
        pcm = resample_int16_mono(frames, src_rate, self.sample_rate)
        chunk_bytes = 320 * 2  # 20ms @16k mono int16
        for i in range(0, len(pcm), chunk_bytes):
            await self.queue.put(pcm[i:i + chunk_bytes])
        await self.queue.put(None)

async def finalize_turn(session_id: str):
    buffer = session_buffers.setdefault(session_id, bytearray())
    if len(buffer) < MIN_BUFFER_BYTES:
        return False
    pipeline = VoicePipeline()
    session_turns[session_id] = session_turns.get(session_id, 0) + 1
    turn_id = session_turns[session_id]
    result = await pipeline.run_once(bytes(buffer))
    session_events[session_id] = {
        'version': 1,
        'session_id': session_id,
        'turn_id': turn_id,
        'state': 'completed',
        'transcript': result['transcript'],
        'response': result['response'],
        'metrics': result['metrics'],
        'has_audio': bool(result['audio']),
        'audio_bytes_len': len(result['audio']) if result['audio'] else 0,
        'updated_at': time.time(),
        'error': None,
        'speaking': False,
    }
    track = session_outbound_tracks.get(session_id)
    if track and result['audio']:
        session_events[session_id]['state'] = 'speaking'
        session_events[session_id]['speaking'] = True
        await track.push_wav_bytes(result['audio'])
        session_events[session_id]['state'] = 'listening'
        session_events[session_id]['speaking'] = False
    buffer.clear()
    return True

async def audio_worker(session_id: str, track: MediaStreamTrack):
    buffer = session_buffers.setdefault(session_id, bytearray())
    session_events[session_id] = {
        'version': 1,
        'session_id': session_id,
        'turn_id': session_turns.get(session_id, 0),
        'state': 'listening',
        'transcript': None,
        'response': None,
        'metrics': None,
        'has_audio': False,
        'audio_bytes_len': 0,
        'updated_at': time.time(),
        'error': None,
        'speaking': False,
    }
    try:
        while True:
            frame = await track.recv()
            pcm = frame_to_mono_int16_bytes(frame)
            src_rate = getattr(frame, 'sample_rate', TARGET_SAMPLE_RATE) or TARGET_SAMPLE_RATE
            pcm = resample_int16_mono(pcm, src_rate, TARGET_SAMPLE_RATE)
            buffer.extend(pcm)
            now = time.time()
            last = session_last_audio_at.get(session_id, now)
            session_last_audio_at[session_id] = now
            session_events[session_id]['state'] = 'receiving_audio'
            session_events[session_id]['updated_at'] = now

            if len(buffer) >= MIN_BUFFER_BYTES and vad.has_speech(bytes(buffer)) and (now - last) >= TURN_IDLE_SECONDS:
                session_events[session_id]['state'] = 'processing'
                await finalize_turn(session_id)
    except Exception as e:
        session_events[session_id] = {
            'version': 1,
            'session_id': session_id,
            'turn_id': session_turns.get(session_id, 0),
            'state': 'error',
            'transcript': None,
            'response': None,
            'metrics': None,
            'has_audio': False,
            'audio_bytes_len': 0,
            'updated_at': time.time(),
            'error': str(e),
            'speaking': False,
        }
        return

@router.get('/health')
async def health():
    return {
        'status': 'ok',
        'transport': 'webrtc',
        'sessions': len(pcs),
        'workers': len(session_workers),
        'outbound_tracks': len(session_outbound_tracks),
        'turn_idle_seconds': TURN_IDLE_SECONDS,
        'min_buffer_bytes': MIN_BUFFER_BYTES,
        'target_sample_rate': TARGET_SAMPLE_RATE,
    }

@router.get('/session/{session_id}/events')
async def session_event(session_id: str):
    return {
        'ok': True,
        'session_id': session_id,
        'event': session_events.get(session_id),
        'has_peer_connection': session_id in pcs,
        'has_worker': session_id in session_workers,
        'has_outbound_track': session_id in session_outbound_tracks,
        'buffer_bytes': len(session_buffers.get(session_id, bytearray())),
    }

@router.post('/session/{session_id}/finalize')
async def finalize_session_turn(session_id: str):
    if session_id not in pcs:
        raise HTTPException(status_code=404, detail='session_not_found')
    session_events.setdefault(session_id, {})['state'] = 'processing'
    completed = await finalize_turn(session_id)
    return {'ok': True, 'session_id': session_id, 'completed': completed, 'event': session_events.get(session_id)}

@router.post('/offer')
async def offer(body: OfferRequest):
    try:
        pc = RTCPeerConnection()
        pcs[body.session_id] = pc
        session_buffers[body.session_id] = bytearray()
        session_turns[body.session_id] = 0

        outbound = OutboundAudioTrack()
        session_outbound_tracks[body.session_id] = outbound
        pc.addTrack(outbound)

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
                session_last_audio_at.pop(body.session_id, None)
                session_outbound_tracks.pop(body.session_id, None)

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
