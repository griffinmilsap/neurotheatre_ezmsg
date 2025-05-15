import ezmsg.core as ez
import numpy as np
import pyaudio
from scipy.signal import resample

class AudioLoopbackSettings(ez.Settings):
    output_sample_rate: int = 44100  # Hz
    block_size: int = 1024


class AudioLoopbackState(ez.State):
    pyaudio_obj: pyaudio.PyAudio = None
    stream: pyaudio.Stream = None

class AudioLoopback(ez.Unit):
    SETTINGS: AudioLoopbackSettings
    STATE: AudioLoopbackState

    def initialize(self) -> None:
        self.STATE.pyaudio_obj = pyaudio.PyAudio()
        self.STATE.stream = self.STATE.pyaudio_obj.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.SETTINGS.output_sample_rate,
            output=True,
        )


    def shutdown(self) -> None:
        if self.STATE.stream is not None:
            self.STATE.stream.stop_stream()
            self.STATE.stream.close()
        if self.STATE.pyaudio_obj is not None:
            self.STATE.pyaudio_obj.terminate()

    @ez.subscriber
    @ez.publisher
    def input(self, signal: np.ndarray) -> ez.OutputStream[np.ndarray]:
        upsampled_signal = resample(signal, int(len(signal) * (self.SETTINGS.output_sample_rate / self.SETTINGS.sample_rate)))
        self.STATE.stream.write(upsampled_signal.astype(np.float32).tobytes())
        return upsampled_signal