import ezmsg.core as ez

from ezmsg.unicorn.device import UnicornSettings
from ezmsg.unicorn.dashboard import UnicornDashboard, UnicornDashboardSettings

from neurotheatre.midiunit import Midi, MidiSettings
from neurotheatre.injector import Injector, InjectorSettings
from ezmsg.sigproc.butterworthfilter import ButterworthFilter, ButterworthFilterSettings

class SignalToMidiSystemSettings(ez.Settings):
    unicorn_settings: UnicornSettings
    injector_settings: InjectorSettings
    butterworth_filter_settings: ButterworthFilterSettings
    midi_settings: MidiSettings

class SignalToMidiSystem(ez.Collection):

    SETTINGS = SignalToMidiSystemSettings

    DASHBOARD = UnicornDashboard()
    INJECTOR = Injector()
    FILTER = ButterworthFilter()
    MIDI = Midi()

    def configure(self) -> None:
        self.DASHBOARD.apply_settings(
            UnicornDashboardSettings(
                device_settings=self.SETTINGS.unicorn_settings
            )
        )
        self.INJECTOR.apply_settings(self.SETTINGS.injector_settings)
        self.FILTER.apply_settings(self.SETTINGS.butterworth_filter_settings)
        self.MIDI.apply_settings(self.SETTINGS.midi_settings)

    def network(self) -> ez.NetworkDefinition:
        return (
            (self.DASHBOARD.OUTPUT_SIGNAL, self.INJECTOR.INPUT_SIGNAL),
            (self.INJECTOR.OUTPUT_SIGNAL, self.FILTER.INPUT_SIGNAL),
            (self.FILTER.OUTPUT_SIGNAL, self.MIDI.INPUT_SIGNAL),
        )