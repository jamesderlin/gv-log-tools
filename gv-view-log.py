#!/usr/bin/env python3

# TODO: Govee temperature logger log viewer
#
# * Parse gvh-titlemap.txt file
# * Load specified (or latest) log from friendly name
# * Tool to trim log files.
# * Tool to email if outside temperature range.

"""
TODO: Documentation
"""

import argparse
import configparser
import datetime
import os
import re
import sys
import typing

class DeviceConfig:
    def __init__(self, *, address, name=None):
        self.address = address.upper()
        self.name = name

    def __str__(self):
        return (f"{self.name} ({self.address})"
                if self.name
                else self.address)

    def short_address(self):
        return self.address.replace(":", "")


def centigrade_to_fahrenheit(degrees_c):
    return degrees_c * 9 / 5 + 32


def parse_config_file(path: str) -> typing.List[DeviceConfig]:
    bluetooth_address_re = re.compile(r"(?:[A-Fa-f0-9]{2}:){5}[A-Fa-f0-9]{2}")
    whitespace_re = re.compile(r"\s+")
    map_file_re = re.compile("".join(
        (r"(?P<address>",
         bluetooth_address_re.pattern,
         r")",
         r"(?:\s+(?P<name>.*))?\s*"),
        ),
    )

    device_configs: typing.List[DeviceConfig] = []

    # Try to parse the config file first in GoveeBTTempLogger's
    # `gvh-titlemap.txt` format, which consists of lines the form:
    # ```
    # ADDRESS NAME
    # ```
    is_simple_config_file = True
    with open(path) as f:
        for line in f:
            if whitespace_re.fullmatch(line):
                continue

            m = map_file_re.fullmatch(line)
            if not m:
                is_simple_config_file = False
                break
            name = m.group("name")
            address = m.group("address")
            if name and address:
                device_configs.append(DeviceConfig(address=address, name=name))

        if is_simple_config_file:
            return device_configs

        # Try ro parse the config file as an `.ini`-like file.
        device_configs.clear()
        f.seek(0)
        config = configparser.ConfigParser(interpolation=None)
        config.read_file(f, source=path)
        for section_name in config:
            if not bluetooth_address_re.fullmatch(section_name):
                continue
            address = section_name
            name = config[section_name].get("name")
            device_configs.append(DeviceConfig(address=address, name=name))

        return device_configs


def main(argv: typing.List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip(), add_help=False)
    ap.add_argument("-h", "--help", action="help",
                    help="Show this help message and exit.")
    ap.add_argument("--date", metavar="YEAR-MONTH", help="TODO")
    ap.add_argument("--config", metavar="CONFIG_FILE", dest="config_file_path",
                    help="TODO")
    ap.add_argument("--header", action=argparse.BooleanOptionalAction,
                    help="TODO")
    ap.add_argument("--units", metavar="UNITS", type=str.lower,
                    choices=("c", "centigrade", "celsius", "f", "fahrenheit"),
                    default="centigrade",
                    help="The temperature units to show.")
    ap.add_argument("--utc", action="store_true",
                    help="Show time as UTC times instead of in the local time.")
    ap.add_argument("name", nargs="?", help="TODO")
    args = ap.parse_args(argv[1:])

    config_file_path = (args.config_file_path
                        or os.path.expanduser("~/.config/gv-tools/gv-tools.rc"))

    device_configs = parse_config_file(config_file_path)

    # TODO: If no query, show interactive prompt.
    query = args.name
    q = query.lower()
    found: typing.List[DeviceConfig] = []
    for config in device_configs:
        if q in str(config).lower():
            found.append(config)

    if not found:
        print(f"\"{query}\" not found in {config_file_path}", file=sys.stderr)
        return 1

    # TODO: Show interactive prompt if there is more than one result.
    config = found[0]

    if args.header is None or args.header:
        print(config)
        print("Date                        Temp.    RH  Battery")

    date = args.date
    if not date:
        now = datetime.datetime.now(tz=datetime.timezone.utc).astimezone()
        date = f"{now.year}-{now.month:02}"

    # TODO: List files and pick latest filename with matching address.
    log_file_path = f"gvh507x_{config.short_address()}-{date}.txt"
    log_line_re = re.compile(r"(?P<timestamp>\d{4}-\d{2}-\d{2}"
                             r"\s+"
                             r"\d{2}:\d{2}:\d{2})"
                             r"\s+"
                             r"(?P<centigrade>[-]?\d+[.]?\d*)"
                             r"\s+"
                             r"(?P<humidity>\d+[.]?\d*)"
                             r"\s+"
                             r"(?P<battery>\d+)"
                             r"\s*")

    with open(log_file_path) as f:
        for line in f:
            m = log_line_re.fullmatch(line)
            if not m:
                continue
            timestamp = (datetime.datetime.fromisoformat(m.group("timestamp"))
                         .replace(tzinfo=datetime.timezone.utc))
            if not args.utc:
                timestamp = timestamp.astimezone()
            centigrade = float(m.group("centigrade"))
            if args.units in ("c", "celsius", "centigrade"):
                degrees = centigrade
                unit_symbol = "C"
            else:
                degrees = centigrade_to_fahrenheit(centigrade)
                unit_symbol = "F"
            humidity = float(m.group("humidity"))
            battery = int(m.group("battery"))
            print(f"{timestamp} "
                  f"{degrees:6.2f}{unit_symbol} "
                  f"{humidity:5.1f}% "
                  f"[{battery:3d}%]")
    return 0


if __name__ == "__main__":
    __name__ = os.path.basename(__file__)  # pylint: disable=redefined-builtin
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(1)
    except BrokenPipeError:
        # From <https://docs.python.org/3/library/signal.html#note-on-sigpipe>:
        #
        # Python flushes standard streams on exit; redirect remaining output
        # to devnull to avoid another BrokenPipeError at shutdown.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)  # Python exits with error code 1 on EPIPE.
