import fcntl
import os
import re
import subprocess
import time
from pathlib import Path
import usb
from config import ac_file, usb_id_whitelist, usb_connected_whitelist, cdrom_drive, battery_file
from config import ethernet_connected_file, bluetooth_paired_whitelist, bluetooth_connected_whitelist, smtp_server
from config import smtp_port, email_sender, email_destination, sender_password, cipher_choice, login_auth
from config import log_file, debug_enable

CONFIG_SEARCH_PATHS = [Path.cwd(), Path.home()]
CONFIG_FILENAME = "config.py"

BT_MAC_REGEX = re.compile(r"(?:[0-9a-fA-F]:?){12}")
BT_PAIRED_REGEX = re.compile(r"(Paired: [0-1])")
BT_NAME_REGEX = re.compile(r"[0-9A-Za-z ]+(?=\s\()")
BT_CONNECTED_REGEX = re.compile(r"(Connected: [0-1])")

POWER_PATH = Path('/sys/class/power_supply')
POWER_DEVICE_TYPES = ['Battery', 'Mains', 'UPS', 'USB']

usb_ids = {}
now_youre_playing_with_power = {}


def detect_bt():
    try:
        bt_command = subprocess.check_output(["bt-device", "--list"],
                                             shell=False).decode()
    except Exception as e:
        print(f'Bluetooth: exception: {str(e)}')
    else:
        # TODO: Clean up
        bt_devices = bt_command.split('\n')
        if len(bt_devices) == 3 and bt_devices[2] == '':
            print('Bluetooth:', bt_command.split('\n')[1])
        else:
            print('Bluetooth:', ', '.join(bt_command.split('\n')[1:]))


def detect_usb():
    usb_ids = {}
    for dev in usb.core.find(find_all=True):
        this_device = f"{hex(dev.idVendor)[2:]:0>4}:{hex(dev.idProduct)[2:]:0>4}"
        if this_device in usb_ids:
            usb_ids[this_device] += 1
        else:
            usb_ids[this_device] = {}
            usb_ids[this_device] = 1
    print('USB:', ', '.join(usb_ids))


def detect_ac():
    devices = ', '.join(power.get_devices(power.DeviceType.MAINS))
    print('AC:', devices if devices else 'none detected')


def detect_battery():
    devices = ', '.join(power.get_devices(power.DeviceType.BATTERY))
    print('Battery:', devices if devices else 'none detected')


def detect_tray():
    disk_tray = cdrom_drive
    fd = os.open(disk_tray, os.O_RDONLY | os.O_NONBLOCK)
    rv = fcntl.ioctl(fd, 0x5326)
    os.close(fd)
    print('CD Tray:', rv)


def detect_ethernet():
    with open(ethernet_connected_file) as ethernet:
        connected = int(ethernet.readline().strip())
    print('Ethernet:', connected)


def read_power_devices():
    for item in POWER_PATH.iterdir():
        filename = item.name
        now_youre_playing_with_power[filename] = {}
        # The uevent file actually has everything we want in one file.
        # Name, status, and type. No reason to load several files when one has all of this.
        device_uevent = Path(item, 'uevent')
        if os.path.isfile(device_uevent):
            with open(device_uevent, 'r') as power_file:
                lines = power_file.readlines()
            for line in lines:
                stripped_line = line.strip().replace('POWER_SUPPLY_', '')
                if stripped_line.startswith('TYPE'):
                    now_youre_playing_with_power[filename]['type'] = stripped_line.replace('TYPE=', '')
                elif stripped_line.startswith('ONLINE'):
                    now_youre_playing_with_power[filename]['online'] = stripped_line.replace('ONLINE=', '')
                elif stripped_line.startswith('PRESENT'):
                    now_youre_playing_with_power[filename]['present'] = stripped_line.replace('PRESENT=', '')
    print(now_youre_playing_with_power)


def read_power_folder():
    for item in POWER_PATH.iterdir():
        print(time.ctime(item))
