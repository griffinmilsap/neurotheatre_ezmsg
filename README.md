# neurotheatre_ezmsg
This repo has EzMsg implementation for neurotheatre project application

This is a uv project.

# Getting Started
install the following packages:
- uv: https://docs.astral.sh/uv/getting-started/installation/
- portaudio (dependency needed for pyaudio, which will be installed by uv). just run `brew install portaudio`

once above is installed, run the following command to setup the environment:
`uv sync`

# Project Structure
.
├── .venv
├── .python-version
├── README.md
├── models
├── main.py
├── pyproject.toml
└── uv.lock

# Project Description
- .venv : This is the virtual environment where uv will install all the packages; Will be created automatically on the root of project when you initialize the project
- models: This contains modules describing individual ezmsg unit implementations, that will be used for final call
- main: Main unit and call to the experiment. when `uv run` command is run, it calls this script