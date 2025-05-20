import ezmsg.core as ez
from ezmsg.util.messages.axisarray import AxisArray
import numpy as np
import pyaudio
from typing import AsyncGenerator

class AudioLoopbackSettings(ez.Settings):
    sample_rate: int = 44100  # Default sample rate for audio playback
    channels: int = 1         # Number of audio channels (e.g., mono = 1, stereo = 2)
    format: int = pyaudio.paFloat32  # Audio format (32-bit float)

class AudioLoopbackState(ez.State):
    audio_stream: pyaudio.Stream = None  # PyAudio stream object
    pyaudio_instance: pyaudio.PyAudio = None  # PyAudio instance

class AudioLoopback(ez.Unit):
    SETTINGS = AudioLoopbackSettings
    STATE = AudioLoopbackState

    INPUT_SIGNAL = ez.InputStream(AxisArray)

    @ez.subscriber(INPUT_SIGNAL)
    async def play_audio(self, msg: AxisArray) -> AsyncGenerator:
        # Initialize PyAudio if not already initialized
        if self.STATE.pyaudio_instance is None:
            self.STATE.pyaudio_instance = pyaudio.PyAudio()
            self.STATE.audio_stream = self.STATE.pyaudio_instance.open(
                format=self.SETTINGS.format,
                channels=self.SETTINGS.channels,
                rate=self.SETTINGS.sample_rate,
                output=True
            )

        # Ensure the input signal is compatible with the audio format
        if 'time' not in msg.axes:
            raise ValueError("Input signal must have a 'time' axis for audio playback.")

        # Reshape the data to match the number of channels
        data = msg.data
        if self.SETTINGS.channels > 1:
            if len(data.shape) == 1:  # If mono, duplicate data for stereo
                data = np.tile(data, (self.SETTINGS.channels, 1)).T
            elif data.shape[1] != self.SETTINGS.channels:
                raise ValueError("Input signal channels do not match the configured audio channels.")

        # Convert data to 32-bit float for PyAudio
        audio_data = data.astype(np.float32).tobytes()

        # Write audio data to the PyAudio stream
        self.STATE.audio_stream.write(audio_data)

    async def shutdown(self):
        # Clean up PyAudio resources on shutdown
        if self.STATE.audio_stream is not None:
            self.STATE.audio_stream.stop_stream()
            self.STATE.audio_stream.close()
        if self.STATE.pyaudio_instance is not None:
            self.STATE.pyaudio_instance.terminate()