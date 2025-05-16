import ezmsg.core as ez

from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings
from ezmsg.unicorn.device import UnicornSettings

from ezmsg.util.messages.axisarray import AxisArray
from ezmsg.util.debuglog import DebugLog


class OSCClientSettings(ez.Settings):
    ...

class OSCClient(ez.Unit):
    SETTINGS = OSCClientSettings

    INPUT_SIGNAL = ez.InputStream(AxisArray)

    async def initialize(self) -> None:
        ...

    @ez.subscriber(INPUT_SIGNAL)
    async def on_signal(self, msg: AxisArray):
        ez.logger.info('Got Data!')

    

class OSCSystemSettings(ez.Settings):
    unicorn_settings: UnicornSettings

class OSCSystem(ez.Collection):

    SETTINGS = OSCSystemSettings

    DASHBOARD = UnicornDashboard()
    LOG = DebugLog()

    def configure(self) -> None:
        self.DASHBOARD.apply_settings(
            UnicornDashboardSettings(
                device_settings = self.SETTINGS.unicorn_settings
            )
        )

    def network(self) -> ez.NetworkDefinition:
        return (
            (self.DASHBOARD.OUTPUT_SIGNAL, self.LOG.INPUT),
        )