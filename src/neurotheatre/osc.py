import typing
import ezmsg.core as ez

from dataclasses import field

from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings
from ezmsg.unicorn.device import UnicornSettings

# from neurotheatre.muse.musedevice import MuseUnit, MuseUnitSettings
# from ezmsg.panel.timeseriesplot import TimeSeriesPlotSettings, TimeSeriesPlot
from ezmsg.util.messages.axisarray import AxisArray
from ezmsg.util.debuglog import DebugLog

from pythonosc.udp_client import SimpleUDPClient

from ezmsg.util.generator import compose
from ezmsg.sigproc.window import windowing
from ezmsg.sigproc.butterworthfilter import butter
from ezmsg.sigproc.affinetransform import common_rereference
from ezmsg.sigproc.downsample import downsample
from ezmsg.sigproc.aggregate import ranged_aggregate
from ezmsg.sigproc.spectrum import spectrum
from ezmsg.sigproc.scaler import scaler_np

from neurotheatre.frequencydecoder import frequency_decode


class EEGOSCSettings(ez.Settings):
    port: int
    address: str = 'localhost'
    time_axis: str = 'time'
    ssvep_freqs: typing.List[float] = field(default_factory = lambda: [7.0, 9.0, 11.0]) # Hz
    bands_tau: float = 5.0 # higher number = more history in bandpower z-score
    bands: typing.Dict[str, typing.Tuple[float, float]] = field(
        default_factory = lambda: {
            'alpha': (8.0, 13.0), # Hz
            'beta': (13.0, 30.0), # Hz
            'gamma': (30.0, 50.0) # Hz
        }
    )


class EEGOSCState(ez.State):
    client: SimpleUDPClient
    preproc: typing.Callable
    norm_bandpower: typing.Callable
    ssvep: typing.Callable

    bands: typing.List[typing.Tuple[float, float]]
    band_names: typing.List[str]

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

        self.STATE.preproc = compose(
            butter(axis = 'time', order = 3, cuton = 1.0, cutoff = 50.0),
            downsample(axis = 'time', factor = 2),
            common_rereference(axis = 'ch'),
        )

        self.STATE.band_names, self.STATE.bands = zip(*self.SETTINGS.bands.items())

        self.STATE.norm_bandpower = compose(
            windowing(axis = 'time', newaxis = 'window', window_dur = 2.0, window_shift = 0.5, zero_pad_until = 'input'),
            spectrum(axis = 'time', out_axis = 'freq'),
            ranged_aggregate(axis = 'freq', bands = self.STATE.bands),
            scaler_np(time_constant = self.SETTINGS.bands_tau, axis = 'window'),
        )

        self.STATE.ssvep = compose(
            windowing(axis = 'time', newaxis = 'window', window_dur = 4.0, window_shift = 0.5, zero_pad_until = 'input'),
            frequency_decode(time_axis = 'time', harmonics = 2, freqs = self.SETTINGS.ssvep_freqs, softmax_beta = 5.0, window_axis = 'window', calc_corrs = True),
        )

    @ez.subscriber(INPUT_SIGNAL)
    async def on_signal(self, msg: AxisArray):
        preproc: AxisArray = self.STATE.preproc(msg)

        # Send processed EEG
        for aa in preproc.iter_over_axis(self.SETTINGS.time_axis):
            self.STATE.client.send_message('/eeg/preproc', aa.data.tolist())

        # Calculate normalized bandpower
        norm_bandpower: AxisArray = self.STATE.norm_bandpower(preproc)
        if norm_bandpower.data.size != 0:
            for band, aa in zip(self.STATE.band_names, norm_bandpower.iter_over_axis('freq')):
                self.STATE.client.send_message(f'/eeg/{band}', aa.data.mean())
                ez.logger.info(f'{band}: {aa.data.mean()}')

        # Calculate SSVEP posteriors
        posteriors = self.STATE.ssvep(preproc)
        if posteriors.data.size != 0:
            probs = posteriors.isel(window = -1).data.flatten()
            freq = self.SETTINGS.ssvep_freqs[probs.argmax().item()]
            prob = probs[probs.argmax().item()].item()
            ez.logger.info(posteriors)
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


# class MuseOSCSystemSettings(ez.Settings):
#     muse_settings: MuseUnitSettings
#     osc_settings: EEGOSCSettings
#     plot_settings: TimeSeriesPlotSettings

# class MuseOSCSystem(ez.Collection):
#     SETTINGS = MuseOSCSystemSettings

#     MUSE = MuseUnit()
#     OSC = EEGOSC()
#     PLOT = TimeSeriesPlot()

#     def configure(self) -> None:
#         self.MUSE.apply_settings(self.SETTINGS.muse_settings)
#         self.OSC.apply_settings(self.SETTINGS.osc_settings)
#         self.PLOT.apply_settings(self.SETTINGS.plot_settings)

#     def network(self) -> ez.NetworkDefinition:
#         return (
#             (self.MUSE.OUTPUT_SIGNAL, self.OSC.INPUT_SIGNAL),  # Connect Muse output to OSC input
#             (self.MUSE.OUTPUT_SIGNAL, self.PLOT.INPUT_SIGNAL),
#         )