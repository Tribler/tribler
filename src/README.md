# Run Tribler

[Full instruction](https://tribler.readthedocs.io/en/latest/development/development.html)

## Install requirements

```
python3 -m pip install -r requirements.txt
```

## Execute Tribler

```
tribler.sh
```

# Run Tests

Install all necessary dependencies:
```
python3 -m pip install -r requirements-test.txt
```
Note: `requirements-test.txt` already contains all requirements 
from` requirements.txt`.

##

Export to PYTHONPATH the following directories:

* tribler-core
* tribler-gui

Shortcut for macOS:
```shell script
export PYTHONPATH=${PYTHONPATH}:`echo {pyipv8,tribler-core,tribler-gui} | tr " " :`
```
Execute:
```
python3 -m pytest tribler-core
python3 -m pytest tribler-gui --guitests
```