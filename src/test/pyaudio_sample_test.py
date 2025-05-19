import pyaudio
import numpy as np
import time

def play_sine_wave(frequency=440, duration=1, volume=0.1):
    """
    Generates and plays a sine wave using PyAudio.

    Args:
        frequency (float): The frequency of the sine wave in Hz.  Default is 440 Hz (A4).
        duration (float): The duration of the sine wave in seconds. Default is 3 seconds.
        volume (float): The volume of the sine wave (0 to 1). Default is 0.5.
    """
    # Audio parameters
    sample_rate = 44100  # Samples per second
    # Calculate the number of frames
    num_frames = int(sample_rate * duration)
    # Generate the time vector
    t = np.linspace(0, duration, num_frames, endpoint=False)
    # Generate the sine wave
    sine_wave = volume * np.sin(2 * np.pi * frequency * t)
    # Convert to 32-bit PCM (PyAudio default)
    audio_data = sine_wave.astype(np.float32).tobytes()
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    try:
        # Open an audio stream for output
        stream = p.open(format=pyaudio.paFloat32,  # 16-bit PCM format
                        channels=1,              # Mono audio
                        rate=sample_rate,
                        output=True)
        # Play the audio data
        stream.write(audio_data)  # Convert to bytes
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
    except Exception as e:
        print(f"Error during audio playback: {e}")
    finally:
        # Terminate PyAudio
        p.terminate()

if __name__ == "__main__":
    print("Playing a sine wave...")
    # Get user input (optional)
    try:
        frequency = float(input("Enter the frequency of the sine wave (Hz, default 440): ") or 440)
        duration = float(input("Enter the duration of the sine wave (seconds, default 1): ") or 1)
        volume = float(input("Enter the volume of the sine wave (0 to 1, default 0.1): ") or 0.1)
        if not 0 <= volume <= 1:
            raise ValueError("Volume must be between 0 and 1.")
    except ValueError as e:
        print(f"Invalid input: {e}. Using default values.")
        frequency = 440
        duration = 1
        volume = 0.1
    # Play the sine wave
    play_sine_wave(frequency, duration, volume)
    print("Sine wave playback complete.")