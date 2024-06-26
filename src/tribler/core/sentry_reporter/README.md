# Tribler Error Reporting with Sentry

For collecting errors from users' machines, we use [Sentry](https://docs.sentry.io/). 
Due to the specific nature of our application, we cannot automatically collect 
errors (which is the default behavior of Sentry). Therefore, we had to modify 
the usual Sentry mechanism.
https://github.com/Tribler/tribler/blob/main/src/tribler/core/sentry_reporter/sentry_reporter.py

The changes we made allow us to control Sentry and limit its error reporting
capabilities. By default, in Tribler, sending Sentry messages is suppressed.
When an error occurs, the user is presented with a dialog where they must explicitly
indicate that the error should be sent to the Tribler team.

## Modified Sentry Modes

The modified Sentry has three operating modes:

```python
class SentryStrategy(Enum):
    """Class describes all available Sentry Strategies

    SentryReporter can work with 3 strategies:
    1. Send reports are allowed
    2. Send reports are allowed with a confirmation dialog
    3. Send reports are suppressed (but the last event will be stored)
    """

    SEND_ALLOWED = auto()
    SEND_ALLOWED_WITH_CONFIRMATION = auto()
    SEND_SUPPRESSED = auto()
```

Immediately after Tribler starts, the mode is set to `SEND_ALLOWED_WITH_CONFIRMATION`. 
As soon as the UI loads, Sentry switches to `SEND_SUPPRESSED`.

`SEND_ALLOWED` is used only on developers' machines if they explicitly set 
`TRIBLER_TEST_SENTRY_URL` in the environment variables.

## Scrubber

We use an advanced Scrubber to remove all sensitive parts from the user's report. 
Our Scrubber processes all fields of the Sentry event and replaces sensitive parts 
with placeholders.

Parts considered sensitive:
- User name
- User machine name
- User-specific folder names
- IP addresses
- Torrent hashes

For placeholders, we use words generated by [Faker](https://pypi.org/project/Faker/) 
based on the string. This way, we can understand when the same strings repeat in 
the report, but we cannot determine what the actual value of the string was on 
the user's machine.

https://github.com/Tribler/tribler/blob/main/src/tribler/core/sentry_reporter/sentry_scrubber.py
