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
