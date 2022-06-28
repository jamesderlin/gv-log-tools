#!/usr/bin/env python3

# TODO:
# * Documentation.
# * Error messages.

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


# Untested with earlier versions.
if not gvutils.has_python_version(__file__, (3, 8, 0)):
   sys.exit(1)


def main(argv: typing.List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip(), add_help=False)
    ap.add_argument("-h", "--help", action="help",
                    help="Show this help message and exit.")
    ap.add_argument("--date", metavar="YEAR-MONTH",
                    help="The year and month to print logs for.  If not "
                         "specified, prints the log for the current month.")
    ap.add_argument("--config", metavar="CONFIG_FILE", dest="config_file_path",
                    help=f"The path to the configuration file.  This may be "
                         f"GoveeBTTempLogger's `gvh-titlemap.txt` file.  If "
                         f"not specified, defaults to "
                         f"`{gvutils.Config.default_config_file_path}`.")
    ap.add_argument("--header", metavar="VALUE", nargs="?", type=int,
                    choices=(0, 1), default=1,
                    help="Set to `0` to suppress printing the device name and "
                         "column headings; set to `1` (the default) to print "
                         "them.")
    ap.add_argument("--log-directory",
                    help="Path to the directory containing "
                         "GoveeBTTempLogger's log files.")
    ap.add_argument("--units", metavar="UNITS", type=str.lower,
                    choices=("c", "centigrade", "celsius", "f", "fahrenheit"),
                    default="centigrade",
                    help="The temperature units to show.")
    ap.add_argument("--utc", action="store_true",
                    help="Show times as UTC times instead of in the local "
                         "time.")
    ap.add_argument("name", nargs="?", default="", help="TODO")
    args = ap.parse_args(argv[1:])

    query = args.name

    config = gvutils.Config(args.config_file_path)

    log_directory = args.log_directory or config.log_directory or os.getcwd()
    if not os.path.isdir(log_directory):
        raise gvutils.AbortError(f"\"{log_directory}\" is not a directory.")

    # If there's no explicit query, we'll list all known devices.  Retrieve
    # all known Bluetooth addresses from the filenames of existing logs.
    addresses = gvutils.addresses_from_logs(log_directory)
    if not addresses:
        raise gvutils.AbortError(f"No log files found in {log_directory}")

    # Merge found addresses into the ones specified by the configuration
    # file.
    # TODO: Exclude addresses with no logs?
    for address in sorted(addresses.keys()):
        if address in config.devices:
            continue
        config.devices[address] = gvutils.DeviceConfig(address=address)

    q = query.lower()
    found: typing.List[gvutils.DeviceConfig] = []
    for device in config.devices.values():
        if q in str(device).lower():
            found.append(device)

    if not found:
        assert query
        raise gvutils.AbortError(f"\"{query}\" not found in "
                                 f"{config.config_file_path}")

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

    prefix = addresses.get(device_config.address)
    if not prefix:
        raise gvutils.AbortError(f"No log files found in {log_directory} for "
                                 f"address {device_config.address}.")
    log_file_path = os.path.join(log_directory, f"{prefix}{date}.txt")
    if not os.path.isfile(log_file_path):
        raise gvutils.AbortError(f"No log file found for the specified device "
                                 f"and date: {log_file_path}")

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
                degrees = gvutils.fahrenheit_from_centigrade(centigrade)
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
    except gvutils.AbortError as e:
        if not e.cancelled:
            print(f"{__name__}: {e}", file=sys.stderr)
        sys.exit(e.exit_code)
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
