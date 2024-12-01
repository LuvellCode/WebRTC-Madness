import logging

import fractions
import numpy as np
from av import AudioFrame
import pyaudiowpatch as pyaudio

from aiortc import MediaStreamTrack

from .classes.BetterLog import BetterLog


# class _CombinedMeta(type(MediaStreamTrack), type(BetterLog)):
#     pass



class CustomAudioTrack(MediaStreamTrack, BetterLog):
    """
    By Default: Uses Microphone
    """
    kind = "audio"

    def __init__(self, logger: logging.Logger, rate=48000, channels=2, frames_per_buffer=960):
        MediaStreamTrack.__init__(self)
        BetterLog.__init__(self, logger=logger)
        # super().__init__(logger=logger)  # initializes both supers

        self.rate = rate
        self.channels = channels
        self.frames_per_buffer = frames_per_buffer

        self._timestamp = 0

        self.pa = pyaudio.PyAudio()

        self.stream_parameters = {
            "format": pyaudio.paInt16,
            "channels": self.channels,
            "rate": self.rate,
            "input": True,
            "frames_per_buffer": self.frames_per_buffer
        }

        self.open_stream()

    def open_stream(self):
        self.log_debug(f"Opening the stream with parameters: {self.stream_parameters}")
        self.stream = self.pa.open(**self.stream_parameters)

    def stream_read(self):
        data = np.frombuffer(self.stream.read(self.frames_per_buffer), 
                             dtype=np.int16)
        data = data.reshape(-1, 1).T
        return data

    async def recv(self):
        data = self.stream_read()

        self._timestamp += self.frames_per_buffer
        pts = self._timestamp
        time_base = fractions.Fraction(1, self.rate)
        
        audio_frame = AudioFrame.from_ndarray(data, format='s16', layout='stereo')
        audio_frame.sample_rate = self.rate
        audio_frame.pts = pts
        audio_frame.time_base = time_base

        return audio_frame

    def __del__(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()

class MicrophoneAudioTrack(CustomAudioTrack):
    pass

class LoopbackAudioTrack(CustomAudioTrack):
    def open_stream(self):

        device_index = self.pa.get_default_wasapi_loopback().get("index")
        device = self.pa.get_device_info_by_index(device_index)
        self.log_debug(f"Found Loopback device: {device}")

        self.stream_parameters["input_device_index"] = device_index
        return super().open_stream()
