import typing
import ezmsg.core as ez
import numpy as np

from scipy.spatial.transform import Rotation

from dataclasses import field

from vqf import VQF

from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings
from ezmsg.unicorn.device import UnicornSettings

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
from ezmsg.sigproc.filter import filtergen
from ezmsg.sigproc.math.abs import abs

import json
from ezmsg.util.messagecodec import MessageEncoder

from neurotheatre.frequencydecoder import frequency_decode
import struct
import socket

class EEGOSCSettings(ez.Settings):
    td_address: str = '127.0.0.1:8000'
    imu_address: str = '127.0.0.1:9001'
    hand_address: str = '127.0.0.1:8002'

    time_axis: str = 'time'
    ch_axis: str = 'ch'
    ssvep_dur: float = 8.0 # sec
    ssvep_freqs: typing.List[float] = field(default_factory = lambda: [7.0, 9.0, 11.0]) # Hz
    bands_tau: float = 5.0 # higher number = more history in bandpower z-score
    bands: typing.Dict[str, typing.Tuple[float, float]] = field(
        default_factory = lambda: {
            'alpha': (8.0, 13.0), # Hz
            'beta': (13.0, 30.0), # Hz
            'gamma': (30.0, 50.0) # Hz
        }
    )
    jaw_port: int = 8002 # Port for jaw clench detection
    jaw_thresh: float = 20 # Threshold for jaw clench detection in the envelope (in mv)
    imu_port: int = 9001

class EEGOSCState(ez.State):
    preproc: typing.Callable
    bandpower: typing.Callable
    ssvep: typing.Callable
    enveloper: typing.Callable
    vqf: VQF
    bands: typing.List[typing.Tuple[float, float]]
    band_names: typing.List[str]

    td_client: SimpleUDPClient
    imu_client: socket.socket
    hand_client: socket.socket

    last_envelope: float = 0

class EEGOSC(ez.Unit):
    SETTINGS = EEGOSCSettings
    STATE = EEGOSCState

    INPUT_SIGNAL = ez.InputStream(AxisArray)
    INPUT_MOTION = ez.InputStream(AxisArray)

    async def initialize(self) -> None:
        address, port = tuple(self.SETTINGS.td_address.split(':'))
        self.STATE.td_client = SimpleUDPClient(address = address, port = int(port))

        self.STATE.preproc = compose(
            butter(axis = self.SETTINGS.time_axis, order = 3, cuton = 1.0, cutoff = 50.0),
            downsample(axis = self.SETTINGS.time_axis, factor = 2),
            common_rereference(axis = self.SETTINGS.ch_axis),
        )

        self.STATE.band_names, self.STATE.bands = zip(*self.SETTINGS.bands.items())

        self.STATE.bandpower = compose(
            windowing(axis = self.SETTINGS.time_axis, newaxis = 'window', window_dur = 2.0, window_shift = 0.5, zero_pad_until = 'input'),
            spectrum(axis = self.SETTINGS.time_axis, out_axis = 'freq'),
            ranged_aggregate(axis = 'freq', bands = self.STATE.bands),
            butter(axis = 'window', order = 2, cutoff = 0.1)
        )

        self.STATE.ssvep = compose(
            windowing(axis = self.SETTINGS.time_axis, newaxis = 'window', window_dur = 4.0, window_shift = 0.5, zero_pad_until = 'input'),
            frequency_decode(time_axis = self.SETTINGS.time_axis, harmonics = 2, freqs = self.SETTINGS.ssvep_freqs, softmax_beta = 5.0, window_axis = 'window', calc_corrs = True),
        )

        self.STATE.enveloper = compose(
            # 1. Remove Powerline Noise
            butter(axis = self.SETTINGS.time_axis, order = 3, cutoff = 58.0, cuton = 62.0),
            # 2. Temporal Differential
            filtergen(
                axis = self.SETTINGS.time_axis, 
                coefs = (
                    np.array([1.0, -1.0]), 
                    np.array([1.0, 0.0])), 
                coef_type = 'ba'
            ),
            # 3. Rectify
            abs(),
            # 4. Smooth
            butter(axis = self.SETTINGS.time_axis, order = 3, cutoff = 10.0),
            # 5. Downsample
            downsample(axis = self.SETTINGS.time_axis, factor = 10),
            # 6. Average channels
            ranged_aggregate(axis = self.SETTINGS.ch_axis, bands = [(0, 7)]),
        )

        self.STATE.vqf = VQF(1.0)

        self.STATE.hand_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.STATE.imu_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    @ez.subscriber(INPUT_SIGNAL)
    async def on_signal(self, msg: AxisArray):
        preproc: AxisArray = self.STATE.preproc(msg)

        # Send processed EEG
        for aa in preproc.iter_over_axis(self.SETTINGS.time_axis):
            self.STATE.td_client.send_message('/eeg/preproc', aa.data.tolist())

        # Calculate normalized bandpower
        bandpower: AxisArray = self.STATE.bandpower(preproc)

        band_dict: typing.Dict[str, float] = {}
        if bandpower.data.size != 0:
            # ez.logger.info(bandpower)
            for band, aa in zip(self.STATE.band_names, bandpower.iter_over_axis('freq')):
                value = aa.data.mean()
                self.STATE.td_client.send_message(f'/eeg/{band}', value)
                band_dict[band] = value
                ez.logger.info(f'{band}: {value}')

        mean_power = np.mean(np.array([v for v in band_dict.values()])).item()
        for band, value in band_dict.items():
            self.STATE.td_client.send_message(f'/eeg/{band}_norm', value / mean_power)
            ez.logger.info(f'{band}_norm: {value / mean_power}')

        # Calculate SSVEP posteriors
        posteriors = self.STATE.ssvep(preproc)
        if posteriors.data.size != 0:
            probs = posteriors.isel(window = -1).data.flatten()
            freq = self.SETTINGS.ssvep_freqs[probs.argmax().item()]
            prob = probs[probs.argmax().item()].item()
            ez.logger.info(posteriors)
            self.STATE.td_client.send_message("/ssvep/focus", [freq, prob])

        # Calculate Jaw Clench Envelope
        envelope: AxisArray = self.STATE.enveloper(msg)
        if envelope.data.size != 0:
            for aa in envelope.iter_over_axis(self.SETTINGS.time_axis):
                value = aa.data.item()
                self.STATE.td_client.send_message('/eeg/envelope', value)

                # Check if the envelope exceeds the jaw threshold
                # 'rest': 0, 'close': 1, 'open': 2
                hand_packet: typing.Optional[bytes] = None
                if self.STATE.last_envelope <= self.SETTINGS.jaw_thresh and value > self.SETTINGS.jaw_thresh:
                    # Rising Edge
                    hand_packet = b''.join([
                        struct.pack('<B', 1),  # Movement (1 byte), 1 = 'close'
                        struct.pack('<f', 0.5),  # Speed (4 bytes)
                        struct.pack('<H', 100)  # Duration (2 bytes)
                    ])
                elif self.STATE.last_envelope > self.SETTINGS.jaw_thresh and value < self.SETTINGS.jaw_thresh:
                    # Falling Edge
                    hand_packet = b''.join([
                        struct.pack('<B', 0),  # Movement (1 byte), 0 = 'rest'
                        struct.pack('<f', 0.5),  # Speed (4 bytes)
                        struct.pack('<H', 100)  # Duration (2 bytes)
                    ])

                self.STATE.last_envelope = value

                if hand_packet:
                    hand_addr, hand_port = tuple(self.SETTINGS.hand_address.split(':'))
                    self.STATE.hand_client.sendto(hand_packet, (hand_addr, int(hand_port)))

    @ez.subscriber(INPUT_MOTION)
    async def on_motion(self, msg: AxisArray):
        time_axis = msg.ax(self.SETTINGS.time_axis)
        if time_axis.axis.gain != self.STATE.vqf.coeffs['gyrTs']:
            self.STATE.vqf = VQF(time_axis.axis.gain)

        data = msg.as2d(self.SETTINGS.time_axis) # guarantees time axis is dim 0
        acc = np.ascontiguousarray(data[:, :3] * 9.8) # Convert from g to m/s^2
        gyr = np.ascontiguousarray(np.deg2rad(data[:, 3:6])) # Convert from deg/sec to rad/sec

        # Output is quaternions in [w x y z] ("scalar first") format
        orientation = self.STATE.vqf.updateBatch(gyr, acc)['quat6D'][-1, :]
        rotation = Rotation.from_quat(orientation, scalar_first = True)
        pitch, roll, yaw = rotation.as_euler('xyz') / np.pi # (-1.0 - 1.0)

        aa = msg.isel({self.SETTINGS.time_axis: -1})
        self.STATE.td_client.send_message('/imu/accel', aa.data[0:3].tolist())
        self.STATE.td_client.send_message('/imu/gyro', aa.data[3:6].tolist())
        self.STATE.td_client.send_message('/imu/orientation', orientation.flatten().tolist())
        self.STATE.td_client.send_message('/imu/orientation_euler', [yaw, pitch, roll])

        imu_addr, imu_port = self.SETTINGS.imu_address.split(':')
        self.STATE.imu_client.sendto(
            json.dumps(msg, cls = MessageEncoder).encode(), 
            (imu_addr, int(imu_port))
        )


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
