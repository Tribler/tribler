## Tribler application tester

> **_NOTE:_** code moved from: https://github.com/Tribler/application-tester/

This repository hosts code for the Tribler application tester, which aims to automatically test Tribler using code injection.
To run the Tribler application tester, it requires a path to the Tribler executable, for example:

```
python scripts/application_tester/main.py -p "python src/run_tribler.py"
```

Upon start, the application tester will automatically verify whether Tribler has been started correctly and then open a TCP connection to the code injection port.
After that, it will send random actions to the Tribler GUI, which are specified in the `data/action_weights.txt` file.
Each action contains a weight, indicating the probability that it is selected as next action by the application tester.

You can specify how long Tribler should be tested by specifying a `-d` (duration) flag, e.g. to run the application tester for two minutes:

```
export CORE_API_PORT=20100
python scripts/application_tester/main.py -p "python src/run_tribler.py" -d 120 
```

To disable all actions and run Tribler idle, specify the `-s` (silent) flag:

```
export CORE_API_PORT=20100
python scripts/application_tester/main.py -p "python src/run_tribler.py" -s
```

Furthermore, there are several flags to increase resource monitoring.
See the output of `python scripts/application_tester/main.py -h` for more details.

## Authors

* @devos50
* @xoriole
* @kozlovsky
