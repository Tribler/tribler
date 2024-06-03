Tribler config is intended to configure the Tribler instance on both users' machines and developers' machines.

The config can be found at the following locations:
* macOS/Ubuntu: `~/.Tribler/<tribler_version>/triblerd.conf`
* Windows: `%Appdata%\.Tribler\<tribler_version>\triblerd.conf`

The structure of the `triblerd.conf` follows the structure of an [INI file](https://en.wikipedia.org/wiki/INI_file).

The list of sections can be found here: [Tribler Config Sections](https://github.com/Tribler/tribler/blob/main/src/tribler/core/config/tribler_config.py#L40-L55). The settings themselves can be found in the corresponding Settings class.

### Example

For example, general settings are located in the `GeneralSettings` class and can be found here: [GeneralSettings Class](https://github.com/Tribler/tribler/blob/main/src/tribler/core/settings.py#L6-L10).

If we want to change the `version_checker_enabled` value in `GeneralSettings`, we should add the following lines to `triblerd.conf`:

```ini
[general]
version_checker_enabled = True
```