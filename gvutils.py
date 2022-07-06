# gvutils.py
#
# Copyright (C) 2022 James D. Lin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Common utility classes and functions shared among govee_thermometer_utils
scripts.
"""

import collections
import configparser
import enum
import functools
import os
import re
import sys
import typing


bluetooth_address_re = re.compile(r"(?:[A-Fa-f0-9]{2}:){5}[A-Fa-f0-9]{2}")

whitespace_re = re.compile(r"\s+")

temperature_re = re.compile(r"(?P<degrees>[^\s]+)\s*(?P<units>[CF])")

map_file_re = re.compile("".join(
    (r"(?P<address>",
     bluetooth_address_re.pattern,
     r")",
     r"(?:\s+(?P<name>.*))?\s*"),
))

log_filename_re = re.compile(r"(?P<base>"
                             r"gv[A-Za-z0-9]+_"
                             r"(?P<address>[A-Fa-f0-9]{12})-"
                             r")"
                             r"(?P<year>[0-9]{4})-(?P<month>[0-9]{2})"
                             r"\.txt")

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


def has_python_version(
    script_file: str,
    version_tuple: typing.Tuple[int, ...],
) -> bool:
    """
    Returns `True` if the Python version is greater than or equal to the
    specified version, `False` otherwise.
    """
    if sys.version_info < version_tuple:
        print("{name}: Requires Python {version} or greater."
              .format(name=script_file,
                      version=".".join((str(i) for i in version_tuple))),
              file=sys.stderr)
        return False
    return True


class AbortError(Exception):
    """
    A simple exception class to abort program execution.

    If `cancelled` is True, no error message should be printed.
    """
    def __init__(
        self,
        message: typing.Optional[str] = None,
        *,
        cancelled: bool = False,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message
                         or ("Cancelled." if cancelled else "Unknown error"))
        assert exit_code != 0
        self.cancelled = cancelled
        self.exit_code = exit_code


def entrypoint(
    main: typing.Callable[[typing.List[str]], int],
) -> typing.Callable[[typing.List[str]], int]:
    """
    Returns a decorator for top-level `main` (or equivalent) functions.

    Used to reduce boilerplate.
    """
    @functools.wraps(main)
    def wrapper(argv: typing.List[str]) -> int:
        try:
            return main(argv)
        except AbortError as e:
            if not e.cancelled:
                print(f"{__name__}: {e}", file=sys.stderr)
            return e.exit_code
        except KeyboardInterrupt:
            return 1
        except BrokenPipeError:
            # From <https://docs.python.org/3/library/signal.html#note-on-sigpipe>:
            #
            # Python flushes standard streams on exit; redirect remaining output
            # to devnull to avoid another BrokenPipeError at shutdown.
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            return 1  # Python exits with error code 1 on EPIPE.
    return wrapper


def parse_bool(s: str) -> bool:
    """Parses a boolean value from a string."""
    s = s.lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    elif s in ("0", "false", "no", "n", "off"):
        return False
    raise AbortError(f"Invalid boolean value: {s}")


class DeviceConfig:
    """Configuration for a Govee thermometer device."""
    def __init__(
        self,
        *,
        address: str,
        name: typing.Optional[str] = None,
    ) -> None:
        self.address = address.upper()
        self.name = name
        self.min_temperature = None
        self.max_temperature = None

    def __str__(self) -> str:
        return (f"{self.name} ({self.address})"
                if self.name
                else self.address)


class Config:
    """Settings read from the configuration file."""
    default_config_file_path_raw = "~/.config/gv-log-tools/gv-log-tools.rc"

    def __init__(self, path: typing.Optional[str]) -> None:
        """
        Initializes a `Config` object from a path to the specified
        configuration file.

        The specified file may either be a GoveeBTTempLogger `gvh-titlemap.txt`
        file or a `gv-log-tools.rc` `.ini`-like file.

        If no path is specified, uses the default configuration file path.
        """
        self.log_directory = ""
        self.devices: typing.OrderedDict[str, DeviceConfig] = \
            collections.OrderedDict()

        if path:
            if not os.path.isfile(path):
                raise AbortError(f"File not found: {path}")
            self.config_file_path = path
        else:
            self.config_file_path = os.path.expanduser(
                Config.default_config_file_path_raw,
            )
            if not os.path.isfile(self.config_file_path):
                return

        with open(self.config_file_path) as f:
            # Try to parse the config file first as GoveeBTTempLogger's
            # `gvh-titlemap.txt` format.
            device_configs = parse_map_file(f)
            if device_configs is not None:
                self.devices = device_configs
                return

            # Try to parse the config file as an `.ini`-like file.
            self.devices.clear()
            f.seek(0)
            cp = configparser.ConfigParser(interpolation=None)
            try:
                cp.read_file(f, source=self.config_file_path)
            except configparser.MissingSectionHeaderError as e:
                raise AbortError(f"\"{self.config_file_path}\" is not a valid "
                                 f"configuration file.") from e

        if cp.has_section("config"):
            main_section = cp["config"]
            self.log_directory = os.path.expanduser(
                main_section.get("log_directory", "") or "",
            )

            map_file = os.path.expanduser(main_section.get("map_file") or "")
            if map_file:
                try:
                    # pylint: disable=consider-using-with
                    f = open(map_file)
                except OSError as e:
                    raise AbortError(f"Failed to parse {map_file}: "
                                     f"{e.strerror}") from e
                with f:
                    self.devices = (parse_map_file(f)
                                    or collections.OrderedDict())

            self.notify_command = main_section.get("notify_command")

        def parse_entry(
            section: str,
            key: str,
            parse_value: typing.Callable[[str], typing.Any],
        ) -> typing.Any:
            try:
                value = cp[section].get(key)
                if value is None:
                    return None
                return parse_value(value)
            except ValueError as e:
                raise AbortError(f"{e} (for `{key}` in section [{section}] in "
                                 f"{self.config_file_path})") from e

        for section_name in cp:
            if not bluetooth_address_re.fullmatch(section_name):
                continue
            address = section_name
            name = cp[section_name].get("name")

            # Device names from the map file take precedence.
            device = self.devices.setdefault(address,
                                             DeviceConfig(address=address,
                                                          name=name))

            device.min_temperature = parse_entry(section_name,
                                                 "min_temperature",
                                                 Temperature.parse)
            device.max_temperature = parse_entry(section_name,
                                                 "max_temperature",
                                                 Temperature.parse)


def parse_map_file(
    file: typing.TextIO,
) -> typing.Optional[typing.OrderedDict[str, DeviceConfig]]:
    """
    Tries to parse the specified file stream as GoveeBTTempLogger's
    `gvh-titlemap.txt` format, which consists of lines of the form:

    ```
    ADDRESS\tNAME
    ```

    Returns `None` on parsing failure.
    """
    device_configs: typing.OrderedDict[str, DeviceConfig] = \
        collections.OrderedDict()

    for line in file:
        if whitespace_re.fullmatch(line):
            continue

        m = map_file_re.fullmatch(line)
        if not m:
            return None
        name = m.group("name")
        address = m.group("address")
        if name and address:
            device_configs[address] = DeviceConfig(address=address, name=name)

    return device_configs


def generate_log_lookup_table(
    log_directory: str,
) -> typing.Dict[typing.Tuple[int, int], typing.Dict[str, str]]:
    """
    Scans the specified directory for GoveeBTTempLogger log files and returns a
    lookup table that stores their filenames.  The table uses `tuple`s of
    `(year, month)` as the primary keys and Bluetooth addresses as the
    secondary keys.  For example:
    ```
    (2022, 7): {'01:23:45:67:89:AB': 'gvh507x_0123456789AB-2022-07.txt'}
    ```
    """
    log_table: typing.Dict[typing.Tuple[int, int], typing.Dict[str, str]] = {}
    with os.scandir(log_directory) as dir_entries:
        for entry in dir_entries:
            if not entry.is_file():
                continue
            match = log_filename_re.fullmatch(entry.name)
            if not match:
                continue

            address = chunk_address(match.group("address"))
            year = int(match.group("year"))
            month = int(match.group("month"))

            log_table.setdefault((year, month), {})[address] = entry.name

    return log_table


def chunk_address(address: str) -> str:
    """Inserts `:` separators between each octet of a Bluetooth address."""
    assert len(address) == 12
    return ":".join((address[i : (i + 2)] for i in range(0, len(address), 2)))


def fahrenheit_from_centigrade(degrees_c: float) -> float:
    """Converts a temperature from degrees centigrade to degrees Fahrenheit."""
    return degrees_c * 9 / 5 + 32


def centigrade_from_fahrenheit(degrees_f: float) -> float:
    """Converts a temperature from degrees Fahrenheit to degrees centigrade."""
    return (degrees_f - 32) * 5 / 9


class TemperatureUnit(enum.Enum):
    """The preferred unit for measuring temperature."""
    CENTIGRADE = enum.auto()
    FAHRENHEIT = enum.auto()


@functools.total_ordering
class Temperature:
    """A class to represent temperatures."""
    def __init__(
        self,
        *,
        degrees_c: float,
        preferred_unit: TemperatureUnit = TemperatureUnit.CENTIGRADE,
    ) -> None:
        self.degrees_c = degrees_c
        self.preferred_unit = preferred_unit

    @classmethod
    def parse(cls, s: str) -> "Temperature":
        """
        Returns a `Temperature` object parsed from a string.

        Raises `ValueError` if the string is not a valid temperature.

        Examples of accepted inputs:
        ```python
        Temperature.parse("0C")
        Temperature.parse("100.0c")
        Temperature.parse("-18.0F")
        Temperature.parse("98.6f")
        Temperature.parse("451 F")
        ```
        Accepted units are `"C"` and `"F"`.  Case is ignored.
        """
        match = temperature_re.fullmatch(s.strip().upper())
        if not match:
            raise ValueError(f"Invalid temperature: {s}")
        try:
            degrees = float(match.group("degrees"))
        except ValueError as e:
            raise ValueError(f"Invalid temperature: {s}") from e
        units = match.group("units")
        preferred_unit = TemperatureUnit.CENTIGRADE
        if units == "F":
            degrees = centigrade_from_fahrenheit(degrees)
            preferred_unit = TemperatureUnit.FAHRENHEIT
        return Temperature(degrees_c=degrees, preferred_unit=preferred_unit)

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, Temperature)
                and self.degrees_c == other.degrees_c)

    def __lt__(self, other: "Temperature") -> bool:
        return self.degrees_c < other.degrees_c

    def __str__(self) -> str:
        if self.preferred_unit == TemperatureUnit.CENTIGRADE:
            return f"{self.degrees_c:.2f}C"
        else:
            return f"{fahrenheit_from_centigrade(self.degrees_c):.2f}F"
