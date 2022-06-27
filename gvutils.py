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

    def short_address(self) -> str:
        return self.address.replace(":", "")


class Config:
    def __init__(self, path: str) -> None:
        self.log_directory = ""
        self.devices: typing.OrderedDict[str, DeviceConfig] = {}

        if not os.path.isfile(path):
            return

        # Try to parse the config file first in GoveeBTTempLogger's
        # `gvh-titlemap.txt` format, which consists of lines the form:
        # ```
        # ADDRESS NAME
        # ```
        with open(path) as f:
            device_configs = parse_map_file(f)
            if device_configs is not None:
                self.devices = device_configs
                return

            # Try to parse the config file as an `.ini`-like file.
            self.devices.clear()
            f.seek(0)
            cp = configparser.ConfigParser(interpolation=None)
            cp.read_file(f, source=path)

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
    f: typing.TextIO,
) -> typing.Optional[typing.OrderedDict[str, DeviceConfig]]:
    device_configs: typing.OrderedDict[str, DeviceConfig] = {}

    # Try to parse the config file first in GoveeBTTempLogger's
    # `gvh-titlemap.txt` format, which consists of lines the form:
    # ```
    # ADDRESS NAME
    # ```
    for line in f:
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
    return ":".join((address[i : (i + 2)] for i in range(0, len(address), 2)))


def centigrade_to_fahrenheit(degrees_c):
    return degrees_c * 9 / 5 + 32
