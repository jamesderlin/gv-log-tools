# gv-log-tools

Utility scripts for processing log files from [GoveeBTTempLogger] for Govee
Bluetooth thermometers.

* `gv-view-log`: A tool to more easily view logs from GoveeBTTempLogger and
  in a friendlier format.  Allows viewing logs for the thermometer with the
  specified name and date and prints timestamps in the local timezone.

* `gv-notify`: Generates notifications if a Govee thermometer reports values
  outside of an expected range.  Expected to be executed periodically (such as
  via `cron`).


## Installation

Prerequisites:

* [GoveeBTTempLogger].
* Python 3.8 or greater.

`gv-log-tools` depends on Git submodules, so `--recurse-submodules` is
necessary when using `git clone`:

```shell
git clone --recurse-submodules https://github.com/jamesderlin/gv-log-tools.git
```

Optionally add a `~/.config/gv-log-tools/gv-log-tools.rc` file:

```ini
[common]
# Optional.  The GoveeBTTempLogger title map file.  If specified, overrides
# any user-friendly names specified in this file.
map_file=/var/www/html/goveebttemplogger/gvh-titlemap.txt

# Optional.  The default log directory used by GoveeBTTempLogger.  If not
# specified, read logs from the current directory.
log_directory=/var/log/goveebttemplogger

# Optional.  The default expected temperature range for all thermometers.
# Temperatures outside of this range will be reported by `gv-notify`.
# Temperatures may be expressed in Celsius or Fahrenheit.  The range may be
# expressed by a minimum, a maximum, or both.
#
# These entries may be overridden by device-specific ones.
min_temperature=0C
max_temperature=40F

# Optional.  The default expected humidity range for all thermometers.
# Humidity values outside of this range will be reported by `gv-notify`.
# The range may be expressed by a minimum, a maximum, or both.
#
# These entries may be overridden by device-specific ones.
min_humidity=0%
max_humidity=100%

# Optional.  The default minimum battery level expected for all devices.
# Battery levels below this value will be reported by `gv-notify`.
#
# This may be overridden by a device-specific entry.
min_battery=10%

# Configuration for `gv-notify`.
[notify]
command=/usr/bin/mailx -s "Govee thermometer warning" james@example.com

# A Bluetooth address for a Govee thermometer.
[A4:C1:38:01:23:45]
# Optional.  User-friendly name.
name=Kitchen Refrigerator

[A4:C1:38:67:89:AB]
name=Garage Chest Freezer

# Optional.  A device-specific override for the expected temperature range.
min_temperature=
max_temperature=-10C
```


## Examples

```
$ gv-view-log garage  # Show the current log for a device named with "garage".
Garage Chest Freezer (A4:C1:38:67:89:AB)
Date                         Temp.     RH   Battery
2022-06-20 15:42:48-07:00  -15.49C   86.3%  [ 35%]
2022-06-20 17:19:33-07:00  -16.29C   85.5%  [ 34%]
2022-06-20 17:28:35-07:00  -15.59C   86.4%  [ 35%]
...

# If there's no search query or if the query is ambiguous, prompt.
$ gv-view-log
Govee thermometers found for 2022-06:
  1: Kitchen Refrigerator (A4:C1:38:01:23:45)
  2: Garage Chest Freezer (A4:C1:38:67:89:AB)
[1, 2]: 1
Kitchen Refrigerator (A4:C1:38:01:23:45)
Date                         Temp.     RH   Battery
2022-06-20 13:17:12-07:00    1.22C   24.1%  [ 70%]
2022-06-20 14:15:47-07:00    2.33C   26.0%  [ 64%]
2022-06-20 14:16:07-07:00    2.33C   26.2%  [ 64%]
...

```

---

Copyright © 2022 James D. Lin.


[GoveeBTTempLogger]: https://github.com/wcbonner/GoveeBTTempLogger/
