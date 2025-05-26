import ezmsg.core as ez
from ezmsg.util.messages.axisarray import AxisArray
from typing import AsyncGenerator
import numpy as np
from bleak import BleakScanner
from muselsl import list_muses, stream
from pylsl import StreamInlet, resolve_byprop

class MuseUnitSettings(ez.Settings):
    muse_name: str = None  # Name of the Muse device to connect to (None for auto-detection)
    axis: str = "time"     # Axis name for the time dimension
    sampling_rate: float = 256.0  # Sampling rate of the Muse device (default: 256 Hz)
    blocksize: int = 10    # Number of samples per block


class MuseUnitState(ez.State):
    inlet: StreamInlet = None  # LSL inlet for receiving data


class MuseUnit(ez.Unit):
    SETTINGS = MuseUnitSettings
    STATE = MuseUnitState

    OUTPUT_SIGNAL = ez.OutputStream(AxisArray)

    async def initialize(self) -> None:
        # Discover Muse devices using BleakScanner
        print("Scanning for Muse devices. Please wait upto 10 seconds.")
        devices = await BleakScanner.discover(timeout=10.0)  # Set a timeout for scanning
        if not devices:
            raise RuntimeError("No Muse devices found. Please ensure your Muse is powered on and discoverable.")
        muses = [device for device in devices if "Muse" in device.name]
        if not muses:
            raise RuntimeError("No Muse devices found. Please ensure your Muse is powered on and discoverable.")

        muse_name = self.SETTINGS.muse_name
        # Select muse from either the muse_name or 
        # the first available Muse device if muse_name is None
        muse = next((m for m in muses if m.name == muse_name), muses[0])
        print(f"Starting stream for Muse: {muse.name} at {muse.address}")
        stream(muse.address)

        # Resolve the LSL stream
        print("Resolving LSL stream...")
        streams = resolve_byprop("type", "EEG", timeout=5)
        if not streams:
            raise RuntimeError("No LSL stream found. Please ensure the Muse is streaming data.")
        sampling_rate = streams[0].nominal_srate()
        if sampling_rate != self.SETTINGS.sampling_rate:
            self.SETTINGS.sampling_rate = sampling_rate
            print(f"Updated sampling rate to: {sampling_rate} Hz")
        self.STATE.inlet = StreamInlet(streams[0])
        print(f"Connected to LSL stream: {streams[0].name()}")

    @ez.publisher(OUTPUT_SIGNAL)
    async def stream_data(self) -> AsyncGenerator:
        while True:
            # Pull a chunk of data from the LSL stream with the specified blocksize
            # This is a blocking call, so it will wait until data is available
            chunk, timestamps = self.STATE.inlet.pull_chunk(
                timeout=1.0, max_samples=self.SETTINGS.blocksize
            )
            if chunk and timestamps:
                data = np.array(chunk)
                time_axis = np.array(timestamps)

                # Create an AxisArray with the data and time axis
                msg = AxisArray(
                    data=data,
                    axes={
                        self.SETTINGS.axis: AxisArray.LinearAxis(
                            gain=(1.0 / self.SETTINGS.sampling_rate) * self.SETTINGS.blocksize,
                            offset=time_axis[0],
                        )
                    },
                    dims=["time", "channel"],  # Assuming time and channel dimensions
                )

                # Yield the AxisArray as the output signal
                yield self.OUTPUT_SIGNAL, msg

    async def shutdown(self) -> None:
        # Stop the Muse stream (if applicable)
        print("Shutting down Muse stream...")