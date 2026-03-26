import numpy as np

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2  # int16

def frame_to_mono_int16_bytes(frame) -> bytes:
    arr = frame.to_ndarray()
    if arr.ndim == 1:
        mono = arr
    else:
        mono = arr.mean(axis=0)
    mono = mono.astype(np.int16, copy=False)
    return mono.tobytes()

def resample_int16_mono(audio_bytes: bytes, src_rate: int, dst_rate: int = TARGET_SAMPLE_RATE) -> bytes:
    if not audio_bytes or src_rate == dst_rate:
        return audio_bytes
    arr = np.frombuffer(audio_bytes, dtype=np.int16)
    if arr.size == 0:
        return audio_bytes
    duration = arr.size / float(src_rate)
    dst_len = max(1, int(round(duration * dst_rate)))
    src_x = np.linspace(0.0, 1.0, num=arr.size, endpoint=False)
    dst_x = np.linspace(0.0, 1.0, num=dst_len, endpoint=False)
    out = np.interp(dst_x, src_x, arr.astype(np.float32)).astype(np.int16)
    return out.tobytes()
