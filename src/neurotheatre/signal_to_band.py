import ezmsg.core as ez
from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings
from ezmsg.unicorn.device import UnicornSettings
from neurotheatre.waveunit import WaveUnit, WaveUnitSettings

class WaveSystemSettings(ez.Settings):
    wave_settings: WaveUnitSettings
    unicorn_settings: UnicornSettings

class WaveSystem(ez.Collection):
    SETTINGS = WaveSystemSettings

    DASHBOARD = UnicornDashboard()
    WAVE = WaveUnit()

    def configure(self) -> None:
        self.DASHBOARD.apply_settings(
            UnicornDashboardSettings(
                device_settings=self.SETTINGS.unicorn_settings
            )
        )
        self.WAVE.apply_settings(self.SETTINGS.wave_settings)

    def network(self) -> ez.NetworkDefinition:
        return (
            # Connect UnicornDashboard's OUTPUT_SIGNAL to WaveUnit's INPUT_SIGNAL
            (self.DASHBOARD.OUTPUT_SIGNAL, self.WAVE.INPUT_SIGNAL),
        )