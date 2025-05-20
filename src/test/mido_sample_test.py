import mido
from mido import Message
import sys

# Replace 'Your Virtual MIDI Port' with the name of your virtual MIDI port
virtual_port_name = 'GarageBand Virtual In'

# List available MIDI output ports
if virtual_port_name not in mido.get_output_names():
    print("Virtual MIDI port not found. Please check the name.")
    print("Available ports:", mido.get_output_names())
    sys.exit(1)

try:
    # Open the virtual MIDI port
    with mido.open_output(virtual_port_name, virtual=True) as output:
        print(f"Connected to {virtual_port_name}")

        # Example: Send a MIDI note on message (Middle C, velocity 64)
        note_on = Message('note_on', note=60, velocity=64)
        output.send(note_on)
        print("Sent Note On message")

        # Example: Send a MIDI note off message (Middle C, velocity 64)
        note_off = Message('note_off', note=60, velocity=64)
        output.send(note_off)
        print("Sent Note Off message")

except IOError:
    print(f"Could not connect to {virtual_port_name}. Make sure the port is available.")