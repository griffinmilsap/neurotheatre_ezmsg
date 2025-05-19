import ezmsg.core as ez

from ezmsg.unicorn.device import UnicornSettings
from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings

from neurotheatre.audioloopback import AudioLoopbackSettings, AudioLoopback
from neurotheatre.upsample import Upsample, UpsampleSettings
from neurotheatre.injector import Injector, InjectorSettings
from ezmsg.sigproc.butterworthfilter import ButterworthFilter, ButterworthFilterSettings

class SignalToAudioSystemSettings(ez.Settings):
    unicorn_settings: UnicornSettings
    injector_settings: InjectorSettings
    butterworth_filter_settings: ButterworthFilterSettings
    upsample_settings: UpsampleSettings
    audio_settings: AudioLoopbackSettings

class SignalToAudioSystem(ez.Collection):

    SETTINGS = SignalToAudioSystemSettings

    DASHBOARD = UnicornDashboard()
    INJECTOR = Injector()
    FILTER = ButterworthFilter()
    UPSAMPLE = Upsample()
    AUDIOLB = AudioLoopback()

    def configure(self) -> None:
        self.DASHBOARD.apply_settings(
            UnicornDashboardSettings(
                device_settings = self.SETTINGS.unicorn_settings
            )
        )
        self.INJECTOR.apply_settings(self.SETTINGS.injector_settings)
        self.FILTER.apply_settings(self.SETTINGS.butterworth_filter_settings)
        self.UPSAMPLE.apply_settings(self.SETTINGS.upsample_settings)
        self.AUDIOLB.apply_settings(self.SETTINGS.audio_settings)

    def network(self) -> ez.NetworkDefinition:
        return (
            (self.DASHBOARD.OUTPUT_SIGNAL, self.INJECTOR.INPUT_SIGNAL),
            (self.INJECTOR.OUTPUT_SIGNAL, self.FILTER.INPUT_SIGNAL),
            (self.FILTER.OUTPUT_SIGNAL, self.UPSAMPLE.INPUT_SIGNAL),
            (self.UPSAMPLE.OUTPUT_SIGNAL, self.AUDIOLB.INPUT_SIGNAL)
        )