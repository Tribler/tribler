# Run Tribler

Full instruction: [install requirements](https://github.com/Tribler/tribler#setting-up-your-development-environment)

```
python3 -m pip install -r requirements.txt

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

* tribler-common
* tribler-core
* tribler-gui

Execute:
```
python3 -m pytest tribler-core
python3 -m pytest tribler-gui --guitests
```