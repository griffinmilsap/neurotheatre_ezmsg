import ezmsg.core as ez

from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings
from ezmsg.unicorn.device import UnicornSettings

from ezmsg.util.messages.axisarray import AxisArray
from ezmsg.util.debuglog import DebugLog

from pythonosc.udp_client import SimpleUDPClient

from ezmsg.util.generator import compose
from ezmsg.sigproc.window import windowing
from ezmsg.sigproc.butterworthfilter import butter
from ezmsg.sigproc.slicer import slicer
from ezmsg.sigproc.affinetransform import common_rereference

from .frequencydecoder import frequency_decode


class EEGOSCSettings(ez.Settings):
    port: int
    address: str = 'localhost'
    time_axis: str = 'time'

class EEGOSCState(ez.State):
    client: SimpleUDPClient

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

        # freqs = [1000/per for per in [143, 111, 90, 77]] # ~ 7, 9, 11, 13 Hz

        # # Enforce null is always class 0
        # state_labels = ['null'] + [f'{f:0.2f} Hz' for f in freqs]
        # n_states = len(state_labels)
        # n_ch = len(eeg.ax('ch'))

        # cz_ref = np.zeros((n_ch, n_ch))
        # cz_ref[4, :] = -1 # Cz reference
        # cz_ref[np.diag_indices(n_ch)] = 1

        # pipeline = compose(
        #     butter(axis = 'time', order = 3, cuton = 5.0, cutoff = 40.0),
        #     common_rereference(axis = 'ch'),
        #     # affine_transform(cz_ref, axis = 'ch'),
        #     slicer(selection = "5:", axis = 'ch'),
        #     windowing(axis = 'time', newaxis = 'window', window_dur = 4.0, window_shift = 0.5, zero_pad_until = 'input'),
        #     frequency_decode(time_axis = 'time', harmonics = 2, freqs = freqs, softmax_beta = 5.0, window_axis = 'window', calc_corrs = True),
        # )

    @ez.subscriber(INPUT_SIGNAL)
    async def on_signal(self, msg: AxisArray):
        ...

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