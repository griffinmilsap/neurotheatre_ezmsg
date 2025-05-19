# neurotheatre_ezmsg
This repo has EzMsg implementation for neurotheatre project application

This is a uv project.

# Getting Started
install the following packages:
- uv: https://docs.astral.sh/uv/getting-started/installation/
- portaudio (dependency needed for pyaudio, which will be installed by uv). just run `brew install portaudio` for mac

once above is installed, run the following command to setup the environment:
`uv sync`

# Project Structure
```
.
├── .venv
├── README.md
├── src
    └── neurotheatre
    └── test
├── pyproject.toml
└── uv.lock
```

# Project Description
- .venv : This is the virtual environment where uv will install all the packages; Will be created automatically on the root of project when you initialize the project
- src/neurotheatre: This contains modules describing individual ezmsg unit implementations, and collections to create ezmsg network
- main: Main unit and call to the experiment. when `uv run` command is run, it calls this script

# Running the project
currently following commands are implemented
- osc
- toAudio
To run a specific command, do `uv run <command>`

# ENVIRONMENT NOTE
The dependencies are meant to be working on python version 3.10/3.11, which is what is reflected on the pyproject file. Please do not change that