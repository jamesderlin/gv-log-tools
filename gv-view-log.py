#!/usr/bin/env python3

"""
A tool to more easily view logs from GoveeBTTempLogger and in a friendlier
format.
"""
# TODO:
# * Allow customization of columns?

import argparse
import datetime
import os
import re
import sys
import typing

import gvutils
import python_cli_utils


# Untested with earlier versions.
if not gvutils.has_python_version(__file__, (3, 8, 0)):
    sys.exit(1)


def main(argv: typing.List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip(), add_help=False)
    ap.add_argument("-h", "--help", action="help",
                    help="Show this help message and exit.")
    ap.add_argument("--date", metavar="YEAR-MONTH",
                    help="The year and month to print logs for.  If not "
                         "specified, prints the log for the current month.  "
                         "Note that dates are always UTC.")
    ap.add_argument("--config", metavar="CONFIG_FILE", dest="config_file_path",
                    help=f"The path to the configuration file.  This may be "
                         f"GoveeBTTempLogger's `gvh-titlemap.txt` file.  If "
                         f"not specified, defaults to "
                         f"`{gvutils.Config.default_config_file_path}`.")
    ap.add_argument("--header", metavar="VALUE",
                    type=gvutils.parse_bool,
                    default=True,
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
    ap.add_argument("name", metavar="NAME", nargs="?", default="",
                    help="The name (or partial name) of the device to print "
                         "logs for.  If multiple devices are found or if no "
                         "name is specified, prompts will be shown to allow "
                         "selecting a specific device.")
    args = ap.parse_args(argv[1:])

    query = args.name

    config = gvutils.Config(args.config_file_path)

    log_directory = args.log_directory or config.log_directory or os.getcwd()
    if not os.path.isdir(log_directory):
        raise gvutils.AbortError(f"\"{log_directory}\" is not a directory.")

    if args.date:
        date_re = re.compile(r"(?P<year>\d+)-(?P<month>\d+)")
        match = date_re.fullmatch(args.date)
        if not match:
            raise gvutils.AbortError(f"Invalid date.  Date must be in the "
                                     f"form YYYY-MM: {args.date}")
        year = int(match.group("year"))
        month = int(match.group("month"))
    else:
        now = datetime.datetime.now(tz=datetime.timezone.utc).astimezone()
        year = now.year
        month = now.month

    # If there's no explicit query, we'll list all known devices.  Retrieve
    # all known Bluetooth addresses from the filenames of existing logs.
    log_table = gvutils.generate_log_lookup_table(log_directory)
    if not log_table:
        raise gvutils.AbortError(f"No log files found in {log_directory}")

    addresses = log_table.get((year, month))
    if not addresses:
        raise gvutils.AbortError(f"No log files found in {log_directory} for "
                                 f"{year}-{month:02}.")

    # Merge found addresses into the ones specified by the configuration
    # file.
    for address in sorted(addresses.keys()):
        if address in config.devices:
            continue
        config.devices[address] = gvutils.DeviceConfig(address=address)

    q = query.casefold()
    found: typing.List[gvutils.DeviceConfig] = []
    for device in config.devices.values():
        # Exclude addresses with no existing logs.
        if device.address in addresses and q in str(device).casefold():
            found.append(device)

    if not found:
        assert query
        raise gvutils.AbortError(f"No matches to \"{query}\" found.")

    response = python_cli_utils.numbered_choices_prompt(
        [str(device) for device in found],
        preamble=f"Govee thermometers found for {year}-{month:02}:",
        file=sys.stderr,
    )
    if response is None:
        return 1

    device_config = found[response]

    log_file_path = os.path.join(log_directory,
                                 addresses[device_config.address])
    if not os.path.isfile(log_file_path):
        raise gvutils.AbortError(f"No log file found for the specified device "
                                 f"and date: {log_file_path}")

    log_line_re = re.compile(r"^"
                             r"(?P<timestamp>\d{4}-\d{2}-\d{2}"
                             r"\s+"
                             r"\d{2}:\d{2}:\d{2}"
                             r")"
                             r"\s+"
                             r"(?P<centigrade>[^\s]+)"
                             r"\s+"
                             r"(?P<humidity>\d+[.]?\d*)"
                             r"\s+"
                             r"(?P<battery>\d+)"
                             r"(?:"
                             r"\s+"
                             r"(?P<model>[^\s]+)"
                             r"\s+"
                             r"(?P<centigrade2>[^\s]+)"
                             r"\s+"
                             r"(?P<centigrade3>[^\s]+)"
                             r"\s+"
                             r"(?P<centigrade4>[^\s]+)"
                             r")?")

    with open(log_file_path) as f, \
         python_cli_utils.paged_output() as out:
        first = True
        for line in f:
            match = log_line_re.match(line)
            if not match:
                continue
            timestamp = \
                (datetime.datetime.fromisoformat(match.group("timestamp"))
                 .replace(tzinfo=datetime.timezone.utc))
            if not args.utc:
                timestamp = timestamp.astimezone()
            centigrades = [
                float(match.group("centigrade")),
                *(float(s) for s in (match.group(f"centigrade{i}")
                                     for i in range(2, 5))
                  if s)
            ]

            if args.units in ("c", "celsius", "centigrade"):
                degrees = centigrades
                unit_symbol = "C"
            else:
                degrees = [gvutils.fahrenheit_from_centigrade(centigrade)
                           for centigrade in centigrades]
                unit_symbol = "F"

            humidity = float(match.group("humidity"))
            battery = int(match.group("battery"))

            if first and args.header:
                print(device_config, file=out)

                header = "  ".join([
                    "Date                     ",
                    *("  Temp." for i in degrees),
                    "   RH ",
                    "Battery",
                ])
                print(header, file=out)
            first = False

            print(
                "  ".join([
                    f"{timestamp}",
                    *(f"{d:6.2f}{unit_symbol}" for d in degrees),
                    f"{humidity:5.1f}%",
                    f"[{battery:3d}%]",
                ]),
                file=out,
            )
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
