# alpaca-racing-formula-1

## Installation

First clone the repo. Then you have to pull some submodules that poetry depend on in the installation:

```
git submodule update --init --recursive
```

Run `poetry install` to install the virtual environment.

This project requires python `3.7`. You can install this using `pyenv`.

Create the car config files by running in the project folder:

```
donkey createcar mysim
```

Navigate to the mysim folder and open `config.py`. In this file add the following lines:

```
DONKEY_GYM = True
DONKEY_SIM_PATH = "/home/<user-name>/path/to/donkey_sim_file"
DONKEY_GYM_ENV_NAME = "donkey-generated-track-v0"
```
