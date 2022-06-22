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

def parse_map_file(map_file_path: str) -> typing.Dict[str, str]:
    map_file_re = re.compile(r"^"
                             r"(?P<address>(?:[A-Fa-f0-9]{2}:?){6})"
                             r"(?:\s+(?P<name>.*))?"
                             r"\s*$")
    address_dict: typing.Dict[str, str] = {}
    with open(map_file_path) as f:
        for line in f:
            m = map_file_re.match(line)
            if not m:
                continue
            name = m.group("name")
            address = m.group("address")
            if name and address:
                address_dict[address] = name
    return address_dict


def main(argv: typing.List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip(), add_help=False)
    ap.add_argument("-h", "--help", action="help",
                    help="Show this help message and exit.")
    ap.add_argument("--date", metavar="YEAR-MONTH", help="TODO")
    ap.add_argument("--map", metavar="MAP_FILE", dest="map_file_path",
                    required=True,
                    help="TODO")
    ap.add_argument("--header", action=argparse.BooleanOptionalAction,
                    help="TODO")
    ap.add_argument("--units", metavar="UNITS", type=str.lower,
                    choices=("centigrade", "celsius", "fahrenheit"),
                    default="centigrade",
                    help="The temperature units to show.")
    ap.add_argument("--utc", action="store_true",
                    help="Show time as UTC times instead of in the local time.")
    ap.add_argument("name", nargs="?", help="TODO")
    args = ap.parse_args(argv[1:])

    address_dict = parse_map_file(args.map_file_path)

    # TODO: If no query, show interactive prompt.
    query = args.name
    q = query.lower()
    addresses: typing.List[str] = []
    for (a, n) in address_dict.items():
        if q in n.lower():
            addresses.append(a)

    if not addresses:
        print(f"\"{query}\" not found in {map_file_path}", file=sys.stderr)
        return 1

    # TODO: Show interactive prompt if there is more than one result.
    address = addresses[0]

    if args.header is None or args.header:
        print(f"{address_dict[address]} ({address})")
        print("Date                        Temp.    RH  Battery")

    date = args.date
    if not date:
        now = datetime.datetime.now(tz=datetime.timezone.utc).astimezone()
        date = f"{now.year}-{now.month:02}"

    # TODO: List files and pick latest filename with matching address.
    log_file_path = ("gvh507x_{address}-{date}.txt"
                     .format(address=address.replace(":", "").upper(),
                             date=date))
    log_line_re = re.compile(r"^"
                             r"(?P<timestamp>\d{4}-\d{2}-\d{2}"
                             r"\s+"
                             r"\d{2}:\d{2}:\d{2})"
                             r"\s+"
                             r"(?P<centigrade>[-]?\d+[.]?\d*)"
                             r"\s+"
                             r"(?P<humidity>\d+[.]?\d*)"
                             r"\s+"
                             r"(?P<battery>\d+)"
                             r"\s*$")

    with open(log_file_path) as f:
        for line in f:
            m = log_line_re.match(line)
            if not m:
                continue
            timestamp = (datetime.datetime.fromisoformat(m.group("timestamp"))
                         .replace(tzinfo=datetime.timezone.utc))
            if not args.utc:
                timestamp = timestamp.astimezone()
            centigrade = float(m.group("centigrade"))
            if args.units in ("celsius", "centigrade"):
                degrees = centigrade
                unit_symbol = "C"
            else:
                degrees = centigrade * 9 / 5 + 32
                unit_symbol = "F"
            humidity = float(m.group("humidity"))
            battery = int(m.group("battery"))
            print(f"{timestamp} {degrees:6.2f}{unit_symbol} {humidity:5.1f}% [{battery:3d}%]")

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
