import typing
import ezmsg.core as ez

from dataclasses import field

from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings
from ezmsg.unicorn.device import UnicornSettings

from ezmsg.util.messages.axisarray import AxisArray
from ezmsg.util.debuglog import DebugLog

from pythonosc.udp_client import SimpleUDPClient

from ezmsg.util.generator import compose
from ezmsg.sigproc.window import windowing
from ezmsg.sigproc.butterworthfilter import butter
from ezmsg.sigproc.affinetransform import common_rereference

from neurotheatre.frequencydecoder import frequency_decode


class EEGOSCSettings(ez.Settings):
    port: int
    address: str = 'localhost'
    time_axis: str = 'time'
    freqs: typing.List[float] = field(default_factory = lambda: [7.0, 9.0, 11.0])

class EEGOSCState(ez.State):
    client: SimpleUDPClient
    pipeline: typing.Callable

class EEGOSC(ez.Unit):
    SETTINGS = EEGOSCSettings
    STATE = EEGOSCState

    INPUT_SIGNAL = ez.InputStream(AxisArray)
    INPUT_MOTION = ez.InputStream(AxisArray)

    async def initialize(self) -> None:
        self.STATE.client = SimpleUDPClient(
            address = self.SETTINGS.address, 
            port = self.SETTINGS.port
        )

        self.STATE.pipeline = compose(
            butter(axis = 'time', order = 3, cuton = 5.0, cutoff = 40.0),
            common_rereference(axis = 'ch'),
            windowing(axis = 'time', newaxis = 'window', window_dur = 4.0, window_shift = 0.5, zero_pad_until = 'input'),
            frequency_decode(time_axis = 'time', harmonics = 2, freqs = self.SETTINGS.freqs, softmax_beta = 5.0, window_axis = 'window', calc_corrs = True),
        )

    @ez.subscriber(INPUT_SIGNAL)
    async def on_signal(self, msg: AxisArray):
        posteriors = self.STATE.pipeline(msg)
        if posteriors.data.size != 0:
            probs = posteriors.isel(window = -1).data.flatten()
            freq = self.SETTINGS.freqs[probs.argmax().item()]
            prob = probs[probs.argmax().item()].item()
            self.STATE.client.send_message("/ssvep/focus", [freq, prob])

    @ez.subscriber(INPUT_MOTION)
    async def on_motion(self, msg: AxisArray):
        for aa in msg.iter_over_axis(self.SETTINGS.time_axis):
            self.STATE.client.send_message('/imu/accel', aa.data[0:3].tolist())
            self.STATE.client.send_message('/imu/gyro', aa.data[3:6].tolist())


class OSCSystemSettings(ez.Settings):
    osc_settings: EEGOSCSettings
    unicorn_settings: UnicornSettings

class OSCSystem(ez.Collection):

    SETTINGS = OSCSystemSettings

    DASHBOARD = UnicornDashboard()
    OSC = EEGOSC()
    LOG = DebugLog()

    def configure(self) -> None:
        self.DASHBOARD.apply_settings(
            UnicornDashboardSettings(
                device_settings = self.SETTINGS.unicorn_settings
            )
        )
        self.OSC.apply_settings(self.SETTINGS.osc_settings)

    def network(self) -> ez.NetworkDefinition:
        return (
            (self.DASHBOARD.OUTPUT_SIGNAL, self.OSC.INPUT_SIGNAL),
            (self.DASHBOARD.OUTPUT_MOTION, self.OSC.INPUT_MOTION),
        )