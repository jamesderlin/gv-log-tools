#!/usr/bin/env python3

# TODO:
# * Enforce Python version.(Needs 3.9(?) for argparse.BooleanOptionalAction)
# * Documentation.
# * Error messages.
# * Refactor.

"""
TODO: Documentation
"""

import argparse
import datetime
import os
import python_cli_utils
import re
import sys
import typing

import gvutils


def main(argv: typing.List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip(), add_help=False)
    ap.add_argument("-h", "--help", action="help",
                    help="Show this help message and exit.")
    ap.add_argument("--date", metavar="YEAR-MONTH", help="TODO")
    ap.add_argument("--config", metavar="CONFIG_FILE", dest="config_file_path",
                    help="TODO")
    ap.add_argument("--header", action=argparse.BooleanOptionalAction,
                    help="TODO")
    ap.add_argument("--log-directory", help="TODO")
    ap.add_argument("--units", metavar="UNITS", type=str.lower,
                    choices=("c", "centigrade", "celsius", "f", "fahrenheit"),
                    default="centigrade",
                    help="The temperature units to show.")
    ap.add_argument("--utc", action="store_true",
                    help="Show time as UTC times instead of in the local time.")
    ap.add_argument("name", nargs="?", default="", help="TODO")
    args = ap.parse_args(argv[1:])

    query = args.name

    config_file_path = (args.config_file_path
                        or os.path.expanduser("~/.config/gv-tools/gv-tools.rc"))

    config = gvutils.Config(config_file_path)

    log_directory = args.log_directory or config.log_directory or "."
    if not os.path.isdir(log_directory):
        print(f"\"{log_directory}\" is not a directory.", file=sys.stderr)
        return 1

    if not query:
        # If there's no explicit query, we'll list all known devices.  Retrieve
        # all known Bluetooth addresses from the filenames of existing logs.
        log_filename_re = re.compile(r"gv[A-Za-z0-9]+_"
                                     r"(?P<address>[A-Fa-f0-9]{12})-"
                                     r"(?P<year>[0-9]{4})-(?P<month>[0-9]{2})"
                                     r"\.txt")

        addresses: typing.Set[str] = set()
        with os.scandir(log_directory) as dir_entries:
            for entry in dir_entries:
                if not entry.is_file():
                    continue
                match = log_filename_re.fullmatch(entry.name)
                if not match:
                    continue
                addresses.add(match.group("address"))

        # Merge found addresses into the ones specified by the configuration
        # file.
        for address in sorted(addresses):
            chunked = gvutils.chunk_address(address)
            if chunked in config.devices:
                continue
            config.devices[chunked] = gvutils.DeviceConfig(address=chunked)

    q = query.lower()
    found: typing.List[gvutils.DeviceConfig] = []
    for device in config.devices.values():
        if q in str(device).lower():
            found.append(device)

    if not found:
        print(f"\"{query}\" not found in {config_file_path}", file=sys.stderr)
        return 1

    response = python_cli_utils.numbered_choices_prompt(
        found,
        preamble="TODO",  # TODO
        file=sys.stderr,
    )
    if response is None:
        return 1
    device_config = found[response]

    date = args.date
    if not date:
        now = datetime.datetime.now(tz=datetime.timezone.utc).astimezone()
        date = f"{now.year}-{now.month:02}"

    # TODO: List files and pick latest filename with matching address.
    log_file_path = os.path.join(
        log_directory,
        f"gvh507x_{device_config.short_address()}-{date}.txt",
    )
    if not os.path.isfile(log_file_path):
        print(f"No log file found for the specified device and date: "
              f"{log_file_path}",
              file=sys.stderr)
        return 1

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

    with open(log_file_path) as f, \
         python_cli_utils.paged_output() as out:
        if args.header is None or args.header:
            print(device_config, file=out)
            print("Date                         Temp.     RH   Battery",
                  file=out)
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
                degrees = gvutils.centigrade_to_fahrenheit(centigrade)
                unit_symbol = "F"
            humidity = float(m.group("humidity"))
            battery = int(m.group("battery"))
            print(f"{timestamp}  "
                  f"{degrees:6.2f}{unit_symbol}  "
                  f"{humidity:5.1f}%  "
                  f"[{battery:3d}%]",
                  file=out)
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
