from __future__ import annotations

from typing import Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription

router = APIRouter(prefix='/webrtc', tags=['webrtc'])
pcs: Dict[str, RTCPeerConnection] = {}

class OfferRequest(BaseModel):
    sdp: str
    type: str
    session_id: str

@router.get('/health')
async def health():
    return {'status': 'ok', 'transport': 'webrtc', 'sessions': len(pcs)}

@router.post('/offer')
async def offer(body: OfferRequest):
    try:
        pc = RTCPeerConnection()
        pcs[body.session_id] = pc

        @pc.on('connectionstatechange')
        async def on_connectionstatechange():
            if pc.connectionState in {'failed', 'closed', 'disconnected'}:
                await pc.close()
                pcs.pop(body.session_id, None)

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
