"""
TODO: Documentation
"""

import configparser
import os
import re
import sys
import typing


bluetooth_address_re = re.compile(r"(?:[A-Fa-f0-9]{2}:){5}[A-Fa-f0-9]{2}")
whitespace_re = re.compile(r"\s+")
map_file_re = re.compile("".join(
    (r"(?P<address>",
     bluetooth_address_re.pattern,
     r")",
     r"(?:\s+(?P<name>.*))?\s*"),
    ),
)


def has_python_version(
    script_file: str,
    version_tuple: typing.Tuple[int, ...],
) -> bool:
    """
    Returns `True` if the Python version is greater than or equal to the
    specified version, `False` otherwise.
    """
    if sys.version_info < version_tuple:
        print("{name}: Requires Python {version} or newer."
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
    def __init__(self, message=None, *, cancelled=False, exit_code=1):
        super().__init__(message or ("Cancelled."
                                     if cancelled
                                     else "Unknown error"))
        assert exit_code != 0
        self.cancelled = cancelled
        self.exit_code = exit_code


class DeviceConfig:
    def __init__(
        self,
        *,
        address: str,
        name: typing.Optional[str] = None,
    ) -> None:
        self.address = address.upper()
        self.name = name

    def __str__(self) -> str:
        return (f"{self.name} ({self.address})"
                if self.name
                else self.address)


class Config:
    default_config_file_path = os.path.expanduser(
        "~/.config/gv-tools/gv-tools.rc",
    )

    def __init__(self, path: typing.Optional[str]) -> None:
        """
        Initializes a `Config` object from a path to the specified
        configuration file.

        The specified file may either be a GoveeBTTempLogger `gvh-titlemap.txt`
        file or a `gv-tools.rc` `.ini`-like file.

        If no path is specified, uses the default configuration file path.
        """
        self.log_directory = ""
        self.devices: typing.OrderedDict[str, DeviceConfig] = {}

        if path:
            if not os.path.isfile(path):
                raise AbortError(f"File not found: {path}")
            self.config_file_path = path
        elif os.path.isfile(Config.default_config_file_path):
            self.config_file_path = Config.default_config_file_path
        else:
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
            except configparser.MissingSectionHeaderError:
                raise AbortError(f"\"{self.config_file_path}\" is not a valid "
                                 f"configuration file.")

        if cp.has_section("config"):
            main_section = cp["config"]
            self.log_directory = main_section.get("log_directory", "")

            map_file = main_section.get("map_file", "")
            if map_file:
                with open(map_file) as f:
                    self.devices = parse_map_file(f)

        for section_name in cp:
            if not bluetooth_address_re.fullmatch(section_name):
                continue
            address = section_name
            name = cp[section_name].get("name")

            # Device names from the map file take precedence.
            self.devices.setdefault(address, DeviceConfig(address=address,
                                                          name=name))


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
    device_configs: typing.OrderedDict[str, DeviceConfig] = {}

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


def chunk_address(address: str) -> str:
    """Inserts `:` separators between each octet of a Bluetooth address."""
    assert(len(address) == 12)
    return ":".join((address[i : (i + 2)] for i in range(0, len(address), 2)))


def fahrenheit_from_centigrade(degrees_c):
    """Converts a temperature from degrees centigrade to degrees Fahrenheit."""
    return degrees_c * 9 / 5 + 32
