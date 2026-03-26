"""
CrackHire Voice Interview Bot
- VAD: Silero
- STT: OpenAI Whisper
- LLM: Groq/Minimax
- TTS: Piper (local, free)
- Transport: WebSocket
"""

import asyncio
import base64
import logging
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # For Whisper STT
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")  # Optional fallback
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
PIPER_VOICE_PATH = os.environ.get("PIPER_VOICE_PATH", "/home/ubuntu/.openclaw/workspace/backend/data/piper_voices")
PIPER_VOICE = os.environ.get("PIPER_VOICE", "en_US-lessac-medium")

# LLM Config
if GROQ_API_KEY:
    LLM_PROVIDER = "groq"
    LLM_API_KEY = GROQ_API_KEY
    LLM_MODEL = "llama-3.3-70b-versatile"
    LLM_BASE_URL = "https://api.groq.com/openai/v1"
elif MINIMAX_API_KEY:
    LLM_PROVIDER = "minimax"
    LLM_API_KEY = MINIMAX_API_KEY
    LLM_MODEL = "MiniMax-M2.7"
    LLM_BASE_URL = "https://api.minimax.chat/v1"
else:
    LLM_PROVIDER = None
    LLM_API_KEY = ""
    LLM_MODEL = ""

app = FastAPI(title="CrackHire Voice Bot")


class VoicePipeline:
    """Voice processing pipeline: Audio -> STT -> LLM -> TTS"""
    
    def __init__(self):
        self.transcript_buffer = ""
        self.messages = [{"role": "system", "content": """You are a professional interviewer for a software engineering interview.
Ask one brief question at a time. Keep responses under 2 sentences.
Focus on: data structures, algorithms, system design, or past projects."""}]
        self.is_speaking = False
        
    async def transcribe(self, audio_data: bytes) -> str:
        """Convert audio to text using OpenAI Whisper."""
        if not OPENAI_API_KEY:
            logger.warning("No OpenAI API key for Whisper")
            return ""
        
        try:
            import base64
            import aiohttp
            
            # Encode audio to base64
            audio_base64 = base64.b64encode(audio_data).decode()
            
            async with aiohttp.ClientSession() as session:
                url = "https://api.openai.com/v1/audio/transcriptions"
                headers = {
                    "Authorization": f"Bearer {OPENAI_API_KEY}"
                }
                
                # Create form data
                data = aiohttp.FormData()
                data.add_field('file', audio_data, filename='audio.wav', content_type='audio/wav')
                data.add_field('model', 'whisper-1')
                data.add_field('language', 'en')
                
                async with session.post(url, data=data, headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("text", "")
                    else:
                        logger.error(f"Whisper API error: {resp.status}")
        except Exception as e:
            logger.error(f"STT error: {e}")
        return ""
    
    async def chat(self, user_message: str) -> str:
        """Get LLM response."""
        if not LLM_API_KEY:
            return "I'm not configured with an LLM. Please provide API key."
        
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
            
            self.messages.append({"role": "user", "content": user_message})
            
            response = await client.chat.completions.create(
                model=LLM_MODEL,
                messages=self.messages,
                temperature=0.7,
                max_tokens=150
            )
            
            assistant_response = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": assistant_response})
            
            return assistant_response
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return "I encountered an error. Please try again."
    
    async def synthesize(self, text: str) -> bytes:
        """Generate audio from text using Piper."""
        voice_file = Path(PIPER_VOICE_PATH) / f"{PIPER_VOICE}.onnx"
        
        if not voice_file.exists():
            logger.warning(f"Voice file not found: {voice_file}")
            return b""
        
        try:
            from piper import PiperVoice
            import io
            import wave
            
            voice = PiperVoice(str(voice_file))
            audio_buffer = io.BytesIO()
            
            with wave.open(audio_buffer, "wb") as wav_file:
                voice.synthesize_wav(text, wav_file)
            
            audio_buffer.seek(0)
            return audio_buffer.getvalue()
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return b""


@app.websocket("/ws/interview/{interview_id}")
async def websocket_endpoint(websocket: WebSocket, interview_id: str):
    """WebSocket endpoint for voice interviews."""
    await websocket.accept()
    logger.info(f"Client connected: {interview_id}")
    
    pipeline = VoicePipeline()
    audio_buffer = b""
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "audio":
                # Receive audio chunk from client
                audio_chunk = base64.b64decode(data.get("data", ""))
                audio_buffer += audio_chunk
                
            elif msg_type == "stop":
                # Client finished speaking - process audio
                if audio_buffer:
                    await websocket.send_json({
                        "type": "status",
                        "message": "Processing..."
                    })
                    
                    # STT
                    transcript = await pipeline.transcribe(audio_buffer)
                    if transcript:
                        await websocket.send_json({
                            "type": "transcript",
                            "text": transcript
                        })
                        
                        # LLM
                        response = await pipeline.chat(transcript)
                        await websocket.send_json({
                            "type": "response",
                            "text": response
                        })
                        
                        # TTS
                        audio_data = await pipeline.synthesize(response)
                        if audio_data:
                            await websocket.send_json({
                                "type": "audio",
                                "data": base64.b64encode(audio_data).decode(),
                                "format": "wav"
                            })
                    
                    audio_buffer = b""
                    
                    await websocket.send_json({
                        "type": "status",
                        "message": "listening"
                    })
                    
            elif msg_type == "interrupt":
                # User interrupted - stop everything
                audio_buffer = b""
                await websocket.send_json({
                    "type": "interrupt",
                    "status": "stopped"
                })
                
            elif msg_type == "restart":
                # Start new conversation
                pipeline.messages = [{"role": "system", "content": """You are a professional interviewer.
Keep responses brief, 2 sentences max."""}]
                await websocket.send_json({
                    "type": "status",
                    "message": "ready"
                })
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {interview_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except:
            pass


@app.get("/health")
async def health():
    return JSONResponse({
        "status": "healthy",
        "services": {
            "stt": bool(OPENAI_API_KEY),  # Whisper
            "llm": bool(LLM_API_KEY),
            "tts": True
        },
        "config": {
            "stt": "whisper",
            "llm_provider": LLM_PROVIDER,
            "llm_model": LLM_MODEL,
            "tts": "piper",
            "tts_voice": PIPER_VOICE
        }
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7000)