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

Export to the `PYTHONPATH` the `src` directory:

Execute:
```
python3 -m pytest .
python3 -m pytest . --no_parallel
python3 -m pytest . --guitests
```