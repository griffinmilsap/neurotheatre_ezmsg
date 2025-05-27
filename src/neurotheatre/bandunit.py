import ezmsg.core as ez
from ezmsg.util.messages.axisarray import AxisArray
from typing import AsyncGenerator
from dataclasses import field
import numpy as np
from scipy.signal import welch

class BandUnitSettings(ez.Settings):
    time_axis: str = "time"  # Name of the time axis in the signal
    sampling_rate: float = 256.0  # Sampling rate of the input signal
    bands: dict = field(default_factory=lambda: {  # Use default_factory for mutable default
        "delta": (0.5, 4),
        "theta": (4, 8),
        "alpha": (8, 13),
        "beta": (13, 30),
        "gamma": (30, 100),
    })
    # Bands to detect and output True if detected
    # The first element is the band name, 
    # the second is a boolean indicating whether to return True/False or the band name
    detect_band: tuple = ("gamma", False)

class BandUnit(ez.Unit):
    SETTINGS = BandUnitSettings

    INPUT_SIGNAL = ez.InputStream(AxisArray)
    OUTPUT_BAND = ez.OutputStream(str)  # Output the dominant frequency band as a string

    @ez.subscriber(INPUT_SIGNAL)
    @ez.publisher(OUTPUT_BAND)
    async def process_signal(self, msg: AxisArray) -> AsyncGenerator:
        # Ensure the input signal has the specified time axis
        if self.SETTINGS.time_axis not in msg.axes:
            raise ValueError(f"Input signal must have a '{self.SETTINGS.time_axis}' axis.")

        # Iterate over the time axis and process each block
        for block in msg.iter_over_axis(self.SETTINGS.time_axis):
            # Compute the power spectral density (PSD) using Welch's method
            freqs, psd = welch(
                block.data.flatten(),
                fs=self.SETTINGS.sampling_rate,
                nperseg=min(self.SETTINGS.sampling_rate, len(block.data.flatten()))
            )

            # Calculate the power in each frequency band
            band_powers = {}
            for band, (low, high) in self.SETTINGS.bands.items():
                band_mask = (freqs >= low) & (freqs < high)
                band_powers[band] = np.sum(psd[band_mask])

            # Find the dominant frequency band
            dominant_band = max(band_powers, key=band_powers.get)

            # Check if detect_band is set
            target_band, return_bool = self.SETTINGS.detect_band
            if return_bool:
                print(f"Dominant band: {dominant_band} and target band: {target_band}, returning {dominant_band == target_band}")
                # Yield True if the target band is the dominant band, else False
                yield self.OUTPUT_BAND, dominant_band == target_band
            else:
                print(f"Dominant band: {dominant_band} with power {band_powers[dominant_band]}")
                # Yield the dominant frequency band as a string
                yield self.OUTPUT_BAND, dominant_band