import ezmsg.core as ez
from ezmsg.util.messages.axisarray import AxisArray
from typing import AsyncGenerator
import numpy as np

class InjectorSettings ( ez.Settings):
    # Flag to enable the signal injector. 
    # If set to False, injector will just be a pass through.
    # True is meant for simulator and False is meant for actual device
    enabled: bool = False
    freq: float = 14.5

class InjectorState( ez.State ):
    sidx: int = 0 # Sample index

# This class injects and transforms signal from the BCI source
# Useful to generate some dev/test data when enabled
class Injector( ez.Unit ):
    SETTINGS: InjectorSettings
    STATE: InjectorState

    INPUT_SIGNAL = ez.InputStream( AxisArray )
    OUTPUT_SIGNAL = ez.OutputStream( AxisArray )

    @ez.subscriber( INPUT_SIGNAL )
    @ez.publisher ( OUTPUT_SIGNAL )
    async def transform(self, msg: AxisArray ) -> AsyncGenerator:
        if (self.SETTINGS.enabled):
            fs = 1.0 / msg.axes['time'].gain # time axis is in the BCIDecoder source
            t = ( np.arange( msg.data.shape[0]) + self.STATE.sidx) / fs # time in seconds
            #msg.data = np.zeros_like(msg.data)
            msg.data = (msg.data.T + np.sin(2 * np.pi * self.SETTINGS.freq * t)).T # add sin to the random noise from openbci simulator
            yield self.OUTPUT_SIGNAL, msg
            self.STATE.sidx += msg.data.shape[0]
        else:
            yield self.OUTPUT_SIGNAL, msg # Pass through if the Injector is not enabled