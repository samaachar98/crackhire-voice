import asyncio
from app.transports import webrtc

async def run_test():
    sid = 'test-session'
    webrtc.session_events[sid] = {
        'version': 1,
        'session_id': sid,
        'turn_id': 0,
        'state': 'listening',
        'transcript': None,
        'response': None,
        'metrics': None,
        'has_audio': False,
        'audio_bytes_len': 0,
        'updated_at': 0,
        'error': None,
    }
    evt = await webrtc.session_event(sid)
    assert evt['ok'] is True
    assert evt['session_id'] == sid
    assert evt['event']['state'] == 'listening'
    print('EVENT_CONTRACT_OK')

asyncio.run(run_test())
