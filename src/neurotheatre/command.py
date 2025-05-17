import argparse

import ezmsg.core as ez

from ezmsg.unicorn.device import UnicornSettings
from ezmsg.panel.application import Application, ApplicationSettings

from neurotheatre.osc import OSCSystem, OSCSystemSettings, EEGOSCSettings

def osc():

    parser = argparse.ArgumentParser(description = 'unicorn OSC client')
    parser.add_argument('-a', '--address', help = 'remote OSC server address', default = 'localhost')
    parser.add_argument('-p', '--port', help = 'remote OSC server port (UDP)', default = 8000, type = int)
    parser.add_argument('-d', '--device', help = 'device address', default = 'simulator')
    parser.add_argument('--blocksize', help = 'eeg sample block size @ 200 Hz', default = 10, type = int)

    class Args:
        address: str
        port: int
        device: str
        blocksize: int

    args = parser.parse_args(namespace = Args)

    osc = OSCSystem(
        OSCSystemSettings(
            osc_settings = EEGOSCSettings(
                address = args.address,
                port = args.port
            ),
            unicorn_settings = UnicornSettings(
                address = args.device,
                n_samp = args.blocksize
            )
        )
    )

    app = Application(
        ApplicationSettings(
            port = 8888,
            name = 'Neurotheatre'
        )
    )

    app.panels = {
        'osc': osc.DASHBOARD.app,
    }

    ez.run(
        OSC = osc,
        APP = app,
    )