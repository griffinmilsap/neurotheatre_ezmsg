import argparse

import ezmsg.core as ez

from ezmsg.unicorn.device import UnicornSettings
from ezmsg.panel.application import Application, ApplicationSettings

from neurotheatre.osc import OSCSystem, OSCSystemSettings

def osc():

    parser = argparse.ArgumentParser(description = 'unicorn OSC client')

    parser.add_argument('-a', '--address', help = 'device address', default = 'simulator')

    class Args:
        address: str

    args = parser.parse_args(namespace = Args)

    osc = OSCSystem(
        OSCSystemSettings(
            UnicornSettings(
                address = args.address
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