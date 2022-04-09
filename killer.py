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
import asyncio
import os
import sys
from pathlib import Path
from config import sleep_length, debug_enable
import helpers

__author__ = "Lvl4Sword, GhostOfGoes, MarkKoz"
__license__ = "AGPL 3.0"
__version__ = "0.7.1"


async def main():
    while True:
        await helpers.detect_bt(debug)
        await helpers.detect_tray(debug)
        await helpers.detect_ac(debug)
        await helpers.detect_battery(debug)
        await helpers.detect_usb(debug)
        await helpers.detect_ethernet(debug)
        await asyncio.sleep(sleep_length)
        if debug:
            loop.stop()
            break


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="Killer")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Prints all info once, without worrying about shutdown.")
    parser.add_argument("-c", "--config", type=str, default=None,
                        help="Path to a configuration file to use.")
    args = parser.parse_args()

    if args.config:
        config = args.config
    else:
        script_directory = Path(__file__).parent
        config = Path(script_directory, 'config.py')
    if os.path.isfile(config):
        if debug_enable or args.debug:
            debug = True
        else:
            debug = False
        helpers.verify_config()
    else:
        print(f'{config} does not exist')
        sys.exit(1)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
