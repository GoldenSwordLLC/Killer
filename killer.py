#!/usr/bin/env python3
#         _  _  _  _ _
#        | |/ /(_)| | |
#        |   /  _ | | | ____ _ _
#        |  \  | || | |/ _  ) `_|
#        | | \ | || | ( (/_/| |
#        |_|\_\|_|\__)_)____)_|
# _____________________________________
# \                       | _   _   _  \
#  `.                  ___|____________/
#    ``````````````````
# <https://github.com/Lvl4Sword/Killer>
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/agpl.html>.
import argparse
import json
import logging
import pkgutil
import sys
import time
from pathlib import Path
from helpers import detect_bt, detect_tray, detect_ac, detect_battery, detect_usb, detect_ethernet
from config import sleep_length

__author__ = "Lvl4Sword, GhostOfGoes, MarkKoz"
__license__ = "AGPL 3.0"
__version__ = "0.7.1"
LOGO = """
        _  _  _  _ _
       | |/ /(_)| | |
       |   /  _ | | | ____ _ _
       |  \\  | || | |/ _  ) `_|
       | | \\ | || | ( (/_/| |
       |_|\\_\\|_|\\__)_)____)_|
_____________________________________
\\                       | _   _   _  \\
 `.                  ___|____________/
   ``````````````````
"""
power_last_modified = {}


def _load_config(self, config_path: str = None):
    if config_path is None:
        config_file = None
        for path in self.CONFIG_SEARCH_PATHS:
            log.debug(f"Searching for {self.CONFIG_FILENAME} in: {str(path)}")
            file = Path(path, self.CONFIG_FILENAME)
            if file.exists():
                config_file = file
                break
    else:
        config_file = Path(config_path)
        if not config_file.exists():
            log.critical(f"Configuration file '{str(config_file)}' does not exist")
            sys.exit(1)

    if config_file is None:
        log.warning("Didn't find a user-specified configuration, loading the default...")
        try:
            data = pkgutil.get_data('killer', 'config.py')
        # TODO - actually needs an exception
        except
    else:
        data = config_file.read_text(encoding='utf-8')
    try:
        config = json.loads(data)
    except json.JSONDecodeError as ex:
        log.critical("Failed to parse configuration: %s", str(ex))
        sys.exit(1)
    except TypeError:
        config = json.loads(data.decode())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="Killer")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Prints all info once, without worrying about shutdown.")
    parser.add_argument("-c", "--config", type=str, default=None,
                        help="Path to a configuration file to use")
    parser.add_argument("--no-logo", action="store_true",
                        help="Do not display the startup logo")
    args = parser.parse_args()

    if not args.no_logo:
        print(LOGO)

    while True:
        detect_bt()
        detect_tray()
        detect_ac()
        detect_battery()
        detect_usb()
        detect_ethernet()
        if DEBUG:
            break
        else:
            time.sleep(sleep_length)
