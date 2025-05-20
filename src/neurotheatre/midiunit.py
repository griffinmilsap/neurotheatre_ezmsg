import ezmsg.core as ez
from ezmsg.util.messages.axisarray import AxisArray
from typing import AsyncGenerator
import mido
import numpy as np

class MidiSettings(ez.Settings):
    midi_port: str = "VirtualMIDIPort"  # Name of the MIDI output port
    channel: int = 0  # MIDI channel (0-15)
    note_range: tuple = (21, 108)  # MIDI note range (default: piano keys A0 to C8)
    velocity: int = 64  # Default velocity for MIDI notes

class MidiState(ez.State):
    midi_out: mido.ports.BaseOutput = None  # MIDI output port

class Midi(ez.Unit):
    SETTINGS = MidiSettings
    STATE = MidiState

    INPUT_SIGNAL = ez.InputStream(AxisArray)

    @ez.subscriber(INPUT_SIGNAL)
    async def send_midi(self, msg: AxisArray) -> AsyncGenerator:
        # Initialize MIDI output port if not already initialized
        if self.STATE.midi_out is None:
            try:
                self.STATE.midi_out = mido.open_output(self.SETTINGS.midi_port)
            except IOError:
                raise ValueError(f"Could not open MIDI port: {self.SETTINGS.midi_port}")

        # Ensure the input signal has a 'time' axis
        if 'time' not in msg.axes:
            raise ValueError("Input signal must have a 'time' axis for MIDI output.")

        # Normalize the signal to the MIDI note range
        data = msg.data
        min_note, max_note = self.SETTINGS.note_range
        # np.interp does a linear fitting to shift the data to the range of min_note and max_note
        # Clip the values to ensure they are within the MIDI note range
        normalized_data = np.clip(
            np.interp(data, (data.min(), data.max()), (min_note, max_note)),
            min_note,
            max_note
        ).astype(int)

        # Send MIDI note messages
        for note in normalized_data.flatten():
            midi_msg = mido.Message(
                'note_on',
                channel=self.SETTINGS.channel,
                note=note,
                velocity=self.SETTINGS.velocity
            )
            self.STATE.midi_out.send(midi_msg)

    async def shutdown(self):
        # Clean up MIDI resources on shutdown
        if self.STATE.midi_out is not None:
            self.STATE.midi_out.close()