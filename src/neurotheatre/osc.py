import ezmsg.core as ez

from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings
from ezmsg.unicorn.device import UnicornSettings

from ezmsg.util.messages.axisarray import AxisArray
from ezmsg.util.debuglog import DebugLog

from pythonosc.udp_client import SimpleUDPClient


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