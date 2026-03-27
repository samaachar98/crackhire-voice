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
from app.audio.turn_detector import TurnDetector
from app.orchestration.voice_pipeline import VoicePipeline
from app.pipecat.runtime import PipecatRuntimeBootstrap
from app.pipecat.events import make_event

router = APIRouter(prefix='/webrtc', tags=['webrtc'])
pcs: Dict[str, RTCPeerConnection] = {}
session_workers: Dict[str, asyncio.Task] = {}
session_buffers: Dict[str, bytearray] = {}
session_events: Dict[str, dict[str, Any]] = {}
session_turns: Dict[str, int] = {}
session_last_audio_at: Dict[str, float] = {}
session_outbound_tracks: Dict[str, 'OutboundAudioTrack'] = {}
session_interrupts: Dict[str, asyncio.Event] = {}
TURN_IDLE_SECONDS = 1.2
MIN_BUFFER_BYTES = 16000
runtime_bootstrap = PipecatRuntimeBootstrap()
vad = SileroVAD()
turn_detector = TurnDetector(trailing_silence_seconds=0.5)

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

    async def push_wav_bytes(self, wav_bytes: bytes, interrupt_event: Optional[asyncio.Event] = None):
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wav:
            frames = wav.readframes(wav.getnframes())
            src_rate = wav.getframerate()
        pcm = resample_int16_mono(frames, src_rate, self.sample_rate)
        chunk_bytes = 320 * 2
        for i in range(0, len(pcm), chunk_bytes):
            if interrupt_event and interrupt_event.is_set():
                break
            await self.queue.put(pcm[i:i + chunk_bytes])
        await self.queue.put(None)

async def finalize_turn(session_id: str):
    buffer = session_buffers.setdefault(session_id, bytearray())
    if len(buffer) < MIN_BUFFER_BYTES:
        return False
    runtime = runtime_bootstrap
    interrupt_event = session_interrupts.setdefault(session_id, asyncio.Event())
    interrupt_event.clear()
    session_turns[session_id] = session_turns.get(session_id, 0) + 1
    turn_id = session_turns[session_id]
    normalized_audio = runtime.normalize_ingress_audio(bytes(buffer))
    result = await runtime.run_turn(session_id, normalized_audio, interrupt_event)
    if result.get('cancelled'):
        session_events[session_id] = {
            'state': 'interrupted',
            'updated_at': time.time(),
            'events': [
                make_event('turn.interrupted', session_id, turn_id, {'stage': result.get('stage')}),
            ],
            'error': None,
            'speaking': False,
        }
        buffer.clear()
        return False

    session_events[session_id] = {
        'state': 'completed',
        'updated_at': time.time(),
        'events': [
            make_event('transcript.final', session_id, turn_id, {'text': result['transcript']}),
            make_event('response.text', session_id, turn_id, {'text': result['response']}),
            make_event('metrics.turn', session_id, turn_id, result['metrics']),
            make_event('audio.ready', session_id, turn_id, {'has_audio': bool(result['audio']), 'audio_bytes_len': len(result['audio']) if result['audio'] else 0}),
        ],
        'error': None,
        'speaking': False,
    }
    track = session_outbound_tracks.get(session_id)
    if track and result['audio']:
        session_events[session_id]['state'] = 'speaking'
        session_events[session_id]['speaking'] = True
        await track.push_wav_bytes(result['audio'], interrupt_event)
        if interrupt_event.is_set():
            session_events[session_id]['state'] = 'interrupted'
            session_events[session_id]['speaking'] = False
        else:
            session_events[session_id]['state'] = 'listening'
            session_events[session_id]['speaking'] = False
    buffer.clear()
    return True

async def audio_worker(session_id: str, track: MediaStreamTrack):
    buffer = session_buffers.setdefault(session_id, bytearray())
    session_events[session_id] = {
        'state': 'listening',
        'updated_at': time.time(),
        'events': [make_event('state.listening', session_id, session_turns.get(session_id, 0), {})],
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

            # barge-in: if user speech comes in while bot is speaking, interrupt current output/turn
            if vad.has_speech(pcm):
                turn_detector.mark_speech(session_id)
                evt = session_interrupts.setdefault(session_id, asyncio.Event())
                if session_events.get(session_id, {}).get('speaking'):
                    evt.set()
                    session_events[session_id]['state'] = 'interrupted'
                    session_events[session_id]['speaking'] = False

            if len(buffer) >= MIN_BUFFER_BYTES and turn_detector.should_finalize(session_id, now):
                session_events[session_id]['state'] = 'processing'
                await finalize_turn(session_id)
                turn_detector.clear(session_id)
    except Exception as e:
        session_events[session_id] = {
            'state': 'error',
            'updated_at': time.time(),
            'events': [make_event('turn.error', session_id, session_turns.get(session_id, 0), {'message': str(e)})],
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
        session_interrupts[body.session_id] = asyncio.Event()

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
                session_interrupts.pop(body.session_id, None)
                turn_detector.clear(body.session_id)
                runtime_bootstrap.remove_session(body.session_id)

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
