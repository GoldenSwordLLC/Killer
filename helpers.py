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
import fcntl
import os
import re
import smtplib
import socket
import ssl
import subprocess
import sys
import time
from email.mime.text import MIMEText
from pathlib import Path
import usb
from config import ac_file, usb_id_whitelist, usb_connected_whitelist, cdrom_drive, battery_file
from config import ethernet_connected_file, bluetooth_paired_whitelist, bluetooth_connected_whitelist, smtp_server
from config import smtp_port, email_sender, email_destination, sender_password, cipher_choice, login_auth
from config import sleep_length, log_file, debug_enable

BT_CONNECTED_REGEX = re.compile(r"Connected: ([0-1])")
BT_MAC_REGEX = re.compile(r"(?:[0-9a-fA-F]:?){12}")
BT_NAME_REGEX = re.compile(r"Name: ([.0-9A-Za-z ]+)")
BT_PAIRED_REGEX = re.compile(r"Paired: ([0-1])")

POWER_PATH = Path('/sys/class/power_supply')

usb_ids = {}
power_times = {}


async def detect_bt(debug):
    bluetooth_devices = {'paired': {}, 'connected': {}}
    try:
        bt_command = subprocess.check_output(["bt-device", "--list"],
                                             shell=False).decode()
    except Exception as e:
        print(f'Bluetooth: Exception: {str(e)})')
    else:
        device_macs = re.findall(BT_MAC_REGEX, bt_command)
        for mac_address in device_macs:
            device_info = subprocess.check_output(["bt-device", "-i",
                                                  mac_address],
                                                  shell=False).decode()
            device_name = re.findall(BT_NAME_REGEX, device_info)[0]
            device_paired = int(re.findall(BT_PAIRED_REGEX, device_info)[0])
            device_connected = int(re.findall(BT_CONNECTED_REGEX, device_info)[0])
            if device_paired:
                if mac_address in bluetooth_devices['paired']:
                    bluetooth_devices['paired'][mac_address][device_name] += 1
                else:
                    bluetooth_devices['paired'][mac_address] = {}
                    bluetooth_devices['paired'][mac_address][device_name] = 1
            if device_connected:
                if mac_address in bluetooth_devices['connected']:
                    bluetooth_devices['connected'][mac_address][device_name] += 1
                else:
                    bluetooth_devices['connected'][mac_address] = {}
                    bluetooth_devices['connected'][mac_address][device_name] = 1
            if debug:
                print(f'Bluetooth Device Name: {device_name}')
                print(f'Bluetooth Paired: {device_paired}')
                print(f'Bluetooth Connected: {device_connected}')
        if not debug:
            if bluetooth_paired_whitelist != {}:
                paired_devices = bluetooth_devices['paired']
                for paired_mac in paired_devices:
                    try:
                        if bluetooth_paired_whitelist[paired_mac]['name'] != device_name:
                            await kill_the_system(f'Bluetooth Paired Name: {device_name}')
                    except KeyError:
                        await kill_the_system(f'Bluetooth Paired MAC Disallowed: {mac_address}')
            if bluetooth_connected_whitelist != {}:
                if device_connected and mac_address not in bluetooth_connected_whitelist:
                    await kill_the_system(f'Bluetooth Connected MAC Disallowed: {mac_address}')
                elif device_connected and mac_address in bluetooth_connected_whitelist:
                    if bluetooth_connected_whitelist[mac_address]['name'] != device_name:
                        await kill_the_system(f'Bluetooth Connected Name: {device_name}')
        if not debug:
            try:
                for each_mac in bluetooth_devices['paired']:
                    for each_name in bluetooth_devices[each_mac]:
                        actual_amount = bluetooth_devices[each_mac][each_name]
                        if bluetooth_paired_whitelist != {}:
                            expected_p_amount = bluetooth_paired_whitelist[each_mac]['amount']
                            if actual_amount != expected_p_amount:
                                await kill_the_system(
                                    f'Bluetooth Amount: {each_mac} - Actual: {actual_amount} / Expected: {expected_p_amount}')
                        if bluetooth_connected_whitelist != {}:
                            expected_c_amount = bluetooth_connected_whitelist[each_mac]['amount']
                            if actual_amount != expected_c_amount:
                                await kill_the_system(f'Bluetooth Amount: {each_mac} - Actual: {actual_amount} / Expected: {expected_c_amount}')
            except KeyError:
                await kill_the_system(f"Bluetooth: {each_mac} not present in bluetooth_devices['paired']")


async def detect_usb(debug):
    for dev in usb.core.find(find_all=True):
        this_device = f"{hex(dev.idVendor)[2:]:0>4}:{hex(dev.idProduct)[2:]:0>4}"
        if this_device in usb_ids:
            usb_ids[this_device] += 1
        else:
            usb_ids[this_device] = {}
            usb_ids[this_device] = 1
    for each_device in usb_ids:
        if each_device not in usb_id_whitelist:
            await kill_the_system(f'USB Allowed Whitelist:')
        else:
            if usb_id_whitelist[each_device] != usb_ids[each_device]:
                await kill_the_system(f'USB Duplicate Device: {each_device}')
    for each_device in usb_connected_whitelist:
        if each_device not in usb_ids:
            await kill_the_system(f'USB Connected Whitelist: {each_device}')
        else:
            if usb_connected_whitelist[each_device] != usb_ids[each_device]:
                await kill_the_system(f'USB Duplicate Device: {each_device}')


async def detect_ac(debug):
    if ac_file != {}:
        for ac_file_name in ac_file:
            the_ac_file = Path(POWER_PATH, ac_file_name)
            await read_power_file(the_ac_file)
            if not ac_file:
                await kill_the_system('AC')


async def detect_battery(debug):
    for battery in battery_file:
        if battery not in power_times:
            the_battery_file = Path(POWER_PATH, battery)
            status, expected_status = await read_power_file(the_battery_file)
            if status != expected_status:
                await kill_the_system('Battery')
            else:
                power_time = await read_power_time(battery)
                power_times[battery] = power_time
        else:
            power_time = await read_power_time(battery)
            if power_times[battery] != power_time:
                power_times[battery] = power_time
                status, expected_status = await read_power_file(the_battery_file)
                if status != expected_status:
                    await kill_the_system('Battery')
            # No reason to do an else here, considering we know it wasn't
            # changed/altered based off the timestamp :-)


async def detect_tray(debug):
    if cdrom_drive != {}:
        for disk_tray in cdrom_drive:
            try:
                fd = os.open(disk_tray, os.O_RDONLY | os.O_NONBLOCK)
                rv = fcntl.ioctl(fd, 0x5326)
                os.close(fd)
                if rv != cdrom_drive[disk_tray]:
                    await kill_the_system('CD Tray')
            except FileNotFoundError:
                if debug:
                    print(f'Detect Tray: {disk_tray} is not a valid file.')
                else:
                    await kill_the_system('CD Tray')
            except KeyError:
                await kill_the_system('CD Tray')


async def detect_ethernet(debug):
    for ethernet_file in ethernet_connected_file:
        with open(ethernet_file) as the_ethernet_file:
            connected = int(the_ethernet_file.readline().strip())
        if connected != ethernet_connected_file[ethernet_file]:
            await kill_the_system('Ethernet')


async def kill_the_system(warning: str):
    print(warning)
    try:
        await mail_this(warning)
    except socket.gaierror:
        current_time = time.localtime()
        formatted_time = time.strftime('%Y-%m-%d %I:%M:%S%p', current_time)
        try:
            with open(log_file, 'a', encoding='utf-8') as the_log_file:
                the_log_file.write('Time: {0}\nInternet is out.\n'
                                   'Failure: {1}\n\n'.format(formatted_time, warning))
        except FileNotFoundError:
            if debug_enable:
                print(f'Killing The System: {log_file} is not a valid file.')
            else:
                # So this is a tricky one, considering the exception was tripped AND the log file is non-existent.
                # The only real thing we can do here is pass, considering the system's going to shut off anyway.
                pass
    if not debug_enable:
        print('KILLING')
        subprocess.Popen(["/sbin/poweroff", "-f"])


# TODO - Get Jinja templating setup for this
async def mail_this(warning: str):
    subject = f'[Killer: {warning}]'

    current_time = time.localtime()
    formatted_time = time.strftime('%Y-%m-%d %I:%M:%S%p', current_time)

    content = 'Time: {0}\nWarning: {1}'.format(formatted_time, warning)
    msg = MIMEText(content, 'plain')
    msg['Subject'] = subject
    msg['From'] = email_sender
    ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.set_ciphers(cipher_choice)
    ssl_context.options |= ssl.HAS_SNI
    ssl_context.options |= ssl.OP_NO_COMPRESSION
    # No need to explicitly disable SSLv* as it's already been done
    # https://docs.python.org/3/library/ssl.html#id7
    ssl_context.options |= ssl.OP_NO_TLSv1
    ssl_context.options |= ssl.OP_NO_TLSv1_1
    ssl_context.options |= ssl.OP_SINGLE_DH_USE
    ssl_context.options |= ssl.OP_SINGLE_ECDH_USE
    conn = smtplib.SMTP_SSL(smtp_server,
                            port=smtp_port,
                            context=ssl_context)
    conn.esmtp_features['auth'] = login_auth
    conn.login(email_sender, sender_password)
    try:
        for each in email_destination:
            conn.sendmail(email_sender, each, msg.as_string())
    except socket.timeout:
        raise socket.gaierror
    finally:
        conn.quit()


async def read_power_file(the_device):
    power_dict = {}
    device_name = the_device.name
    device_uevent = Path(the_device, 'uevent')
    if os.path.isfile(device_uevent):
        power_dict[device_name] = {}
        with open(device_uevent, 'r') as power_file:
            lines = power_file.readlines()
        for line in lines:
            stripped_line = line.strip().replace('POWER_SUPPLY_', '')
            if stripped_line.startswith('TYPE'):
                power_dict[device_name]['type'] = stripped_line.replace('TYPE=', '')
            elif stripped_line.startswith('ONLINE'):
                power_dict[device_name]['online'] = stripped_line.replace('ONLINE=', '')
            elif stripped_line.startswith('PRESENT'):
                power_dict[device_name]['present'] = stripped_line.replace('PRESENT=', '')
        try:
            # Plugged into the wall
            if power_dict[device_name]['type'] == 'Mains':
                return power_dict[device_name]['online'], ac_file[device_name]
            # Battery, or otherwise UPS
            elif power_dict[device_name]['type'] in ['Battery', 'UPS', 'USB']:
                return power_dict[device_name]['present'], battery_file[device_name]
        except KeyError:
            print(f'Read Power File: {device_name} is not in power_dict')
    else:
        if debug_enable:
            print(f'Read Power File: {device_uevent} is not a valid file.')
        else:
            await kill_the_system('Ethernet')


async def read_power_time(power_device):
    power_path = Path(POWER_PATH, power_device)
    uevent_file = Path(power_path, 'uevent')
    return os.path.getmtime(uevent_file)


def verify_config():
    log_file_good = True
    cdrom_good = True
    initial_types_good = True
    email_destination_good = True
    simple_dict_good = True
    nested_dict_good = True
    files_verified = True
    is_root = True
    config_info = {'ac_file': {},
                   'usb_id_whitelist': {},
                   'usb_connected_whitelist': {},
                   'cdrom_drive': {},
                   'battery_file': {},
                   'ethernet_connected_file': {},
                   'bluetooth_paired_whitelist': {},
                   'bluetooth_connected_whitelist': {},
                   'smtp_server': 'STRING',
                   'smtp_port': 0,
                   'email_sender': 'STRING',
                   'email_destination': [],
                   'sender_password': 'STRING',
                   'cipher_choice': 'STRING',
                   'login_auth': 'STRING',
                   'sleep_length': 1.0,
                   'log_file': 'STRING',
                   'debug_enable': 1}
    simple_dictionary_info = {'ac_file': {'key': 'STRING', 'value': 0},
                              'battery_file': {'key': 'STRING', 'value': 0},
                              'cdrom_drive': {'key': 'STRING', 'value': 0},
                              'ethernet_connected_file': {'key': 'STRING', 'value': 0},
                              'usb_id_whitelist': {'key': 'STRING', 'value': 0},
                              'usb_connected_whitelist': {'key': 'STRING', 'value': 0}}
    nested_dictionary_info = {'bluetooth_paired_whitelist': {'outer_keys': {"USER_SET": 'STRING'},
                                                             'inner_keys': ['name', 'amount'],
                                                             'values': {'name': 'STRING', 'amount': 0}},
                              'bluetooth_connected_whitelist': {'outer_keys': {"USER_SET": 'STRING'},
                                                                'inner_keys': ['name', 'amount'],
                                                                'values': {'name': 'STRING', 'amount': 0}}}
    # list_info = {'email_destination': 'STRING'}
    config_variables = {"ac_file": ac_file, "usb_id_whitelist": usb_id_whitelist,
                        "usb_connected_whitelist": usb_connected_whitelist, "cdrom_drive": cdrom_drive,
                        "battery_file": battery_file, "ethernet_connected_file": ethernet_connected_file,
                        "bluetooth_paired_whitelist": bluetooth_paired_whitelist,
                        "bluetooth_connected_whitelist": bluetooth_connected_whitelist,
                        "smtp_server": smtp_server, "smtp_port": smtp_port, "email_sender": email_sender,
                        "email_destination": email_destination, "sender_password": sender_password,
                        "cipher_choice": cipher_choice, "login_auth": login_auth, "sleep_length": sleep_length,
                        "log_file": log_file, "debug_enable": debug_enable}
    if os.geteuid() != 0:
        print('Killer was not ran with root privileges')
        is_root = False

    # All variables
    for variable in config_info:
        if not isinstance(config_variables[variable], type(config_info[variable])):
            the_type = type(config_info[variable])
            print(f'- {variable} in config.py is not the expected type of {the_type.__name__}')
            initial_types_good = False

    # Specific to email_destination, since that's the only list
    for list_string in config_variables["email_destination"]:
        if not isinstance(list_string, str):
            print(f'- "{list_string}" in "email_destination" is not the expected type of string')
            email_destination_good = False

    # Specific to all simple dictionaries
    for dict_var in simple_dictionary_info:
        for dict_key in list(config_variables[dict_var].keys()):
            if not isinstance(dict_key, str):
                print(f'- "{config_variables[dict_var]}" in config.py is not the expected type of string')
                simple_dict_good = False
        for dict_value in list(config_variables[dict_var].values()):
            if not isinstance(dict_value, int):
                print(f'- "{simple_dictionary_info[dict_var]}" in "{dict_var}" is not the expected type of int')
                simple_dict_good = False

    # Specific to all nested dictionaries
    for nested_dict_var in nested_dictionary_info:
        for nested_dict_key in list(config_variables[nested_dict_var].keys()):
            for internal_dict_key in config_variables[nested_dict_var][nested_dict_key]:
                if internal_dict_key in ['name', 'amount']:
                    if not isinstance(internal_dict_key, str):
                        print(f'- The key "{internal_dict_key}" within the nested dictionary "{nested_dict_var}" in config.py is not the expected type of string')
                        nested_dict_good = False
                    else:
                        this_internal_value = config_variables[nested_dict_var][nested_dict_key][internal_dict_key]
                        if internal_dict_key == 'name':
                            if not isinstance(this_internal_value, str):
                                print(f'- The key "{internal_dict_key}" within the nested dictionary "{nested_dict_var}" in config.py is not the expected type of string')
                                nested_dict_good = False
                        else:
                            if not isinstance(this_internal_value, int):
                                print(f'- The key "{internal_dict_key}" within the nested dictionary "{nested_dict_var}" in config.py is not the expected type of string')
                                nested_dict_good = False
                else:
                    print(f'- {internal_dict_key} is an unexpected internal dict key for {nested_dict_var}.')
                    simple_dict_good = False

    if not all([log_file_good, cdrom_good, initial_types_good,
                email_destination_good, simple_dict_good, nested_dict_good]):
        print('------------------------')
        print('The configuration file is not valid.')
        print('Please remedy the above issue(s).')
        sys.exit(1)
    else:
        if not is_root:
            print('------------------------')
            print('Please remedy the above issue.')
            sys.exit(1)
        else:
            # The configuration file types are what we'd expect, now to verify if the files actually exist..
            if not os.path.isfile(log_file):
                try:
                    with open(log_file, 'a') as log_file_check:
                        current_time = time.localtime()
                        formatted_time = time.strftime('%Y-%m-%d %I:%M:%S%p', current_time)
                        log_file_check.write(f'{formatted_time} - THIS IS A TEST')
                except(FileNotFoundError, PermissionError):
                    print(f'CONFIG: Could not write to non-existent {log_file}.')
                    files_verified = False
                else:
                    print(f'CONFIG: {log_file} was not present, log_file created.')
            for ac in ac_file:
                if not os.path.isdir(Path(POWER_PATH, ac)):
                    print(f'CONFIG: {Path(POWER_PATH, ac)} is NOT present')
                    files_verified = False
            for battery in battery_file:
                if not os.path.isdir(Path(POWER_PATH, battery)):
                    print(f'CONFIG: {Path(POWER_PATH, battery)} is NOT present')
                    files_verified = False
            for ethernet in ethernet_connected_file:
                if not os.path.isfile(ethernet):
                    print(f'CONFIG: {ethernet} is NOT present')
                    files_verified = False
            for disk_tray in cdrom_drive:
                if not os.path.isfile(disk_tray):
                    print(f'CONFIG: {disk_tray} is NOT present')
                    files_verified = False
            if files_verified:
                print('CONFIG: All files/directories have been verified as being present.')
            else:
                sys.exit()
