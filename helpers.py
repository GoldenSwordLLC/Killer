import fcntl
import logging
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
from config import log_file

BT_MAC_REGEX = re.compile(r"(?:[0-9a-fA-F]:?){12}")
BT_PAIRED_REGEX = re.compile(r"(Paired: [0-1])")
BT_NAME_REGEX = re.compile(r"[0-9A-Za-z ]+(?=\s\()")
BT_CONNECTED_REGEX = re.compile(r"(Connected: [0-1])")

POWER_PATH = Path('/sys/class/power_supply')

usb_ids = {}
power_times = {}


def detect_bt():
    try:
        bt_command = subprocess.check_output(["bt-device", "--list"],
                                             shell=False).decode()
    except Exception as e:
        print(f'Bluetooth: none detected (exception: {str(e)})')
    else:
        paired_devices = re.findall(BT_MAC_REGEX, bt_command)
        devices_names = re.findall(BT_NAME_REGEX, bt_command)
        for each in range(0, len(paired_devices)):
            if paired_devices[each] not in bluetooth_paired_whitelist:
                kill_the_system('Bluetooth Paired: {0}'.format(paired_devices[each]))
            else:
                connected = subprocess.check_output(["bt-device", "-i",
                                                    paired_devices[each]],
                                                    shell=False).decode()
                connected_text = re.findall(BT_CONNECTED_REGEX, connected)
                if connected_text[0].endswith("1") and paired_devices[each] not in bluetooth_connected_whitelist:
                    kill_the_system('Bluetooth Connected MAC Disallowed: {0}'.format(paired_devices[each]))
                elif connected_text[0].endswith("1") and each in bluetooth_connected_whitelist:
                    # TODO - This is wrong and needs fixed up
                    if devices_names[each] != bluetooth_paired_whitelist[each]:
                        kill_the_system('Bluetooth Connected Name Mismatch: {0}'.format(devices_names[each]))


def detect_usb():
    usb_ids = {}
    for dev in usb.core.find(find_all=True):
        this_device = f"{hex(dev.idVendor)[2:]:0>4}:{hex(dev.idProduct)[2:]:0>4}"
        if this_device in usb_ids:
            usb_ids[this_device] += 1
        else:
            usb_ids[this_device] = {}
            usb_ids[this_device] = 1
    for each_device in usb_ids:
        if each_device not in usb_id_whitelist:
            kill_the_system(f'USB Allowed Whitelist:')
        else:
            if usb_id_whitelist[each_device] != usb_ids[each_device]:
                kill_the_system(f'USB Duplicate Device: {each_device}')
    for each_device in usb_connected_whitelist:
        if each_device not in usb_ids:
            kill_the_system(f'USB Connected Whitelist: {each_device}')
        else:
            if usb_connected_whitelist[each_device] != usb_ids[each_device]:
                kill_the_system(f'USB Duplicate Device: {each_device}')


# TODO
def detect_ac():
    if not ac_file:
        kill_the_system('AC')


# TODO
def detect_battery():
    if not battery_file:
        kill_the_system('Battery')


# TODO - Don't hard code rv != 1
def detect_tray():
    disk_tray = cdrom_drive
    fd = os.open(disk_tray, os.O_RDONLY | os.O_NONBLOCK)
    rv = fcntl.ioctl(fd, 0x5326)
    os.close(fd)
    if rv != 1:
        kill_the_system('CD Tray')


def detect_ethernet():
    with open(ethernet_connected_file) as ethernet:
        connected = int(ethernet.readline().strip())

    if connected:
        kill_the_system('Ethernet')


def kill_the_system(warning: str):
    try:
        mail_this(warning)
    except socket.gaierror:
        current_time = time.localtime()
        formatted_time = time.strftime('%Y-%m-%d %I:%M:%S%p', current_time)
        with open(log_file, 'a', encoding='utf-8') as the_log_file:
            the_log_file.write('Time: {0}\nInternet is out.\n'
                              'Failure: {1}\n\n'.format(formatted_time, warning))
    subprocess.Popen(["/sbin/poweroff", "-f"])


# TODO - Get Jinja templating setup for this
def mail_this(warning: str):
    subject = f'[ALERT: {warning}]'

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


def read_power_file(the_device):
    power_dict = {}
    device_name = Path(the_device).name
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
        # Plugged into the wall
        if power_dict[device_name]['type'] == 'Mains':
            if power_dict[device_name]['online'] != ac_file[device_name]:
                kill_the_system('AC')
        # Battery, or otherwise UPS
        elif power_dict[device_name]['type'] in ['Battery', 'UPS', 'USB']:
            if power_dict[device_name]['present'] != battery_file[device_name]:
                kill_the_system('Battery')


# TODO
def read_power_folder():
    ac_device = Path(POWER_PATH, ac_file)
    battery_device = Path(POWER_PATH, battery_file)
    print(f'{ac_device}: {os.path.getmtime(ac_device)}')
    print(f'{battery_device}: {os.path.getmtime(battery_device)}')


def verify_config():
    config_good = None
    config_info = {'ac_file': {},
                   'usb_id_whitelist': {},
                   'usb_connected_whitelist': {},
                   'cdrom_drive': 'STRING',
                   'battery_file': {},
                   'ethernet_connected_file': 'STRING',
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
    dictionary_info = {'ac_file': {'type': 'simple', 'key': 'STRING', 'value': 0},
                       'usb_id_whitelist': {'type': 'simple', 'key': 'STRING', 'value': 0},
                       'usb_connected_whitelist': {'type': 'simple', 'key': 'STRING', 'value': 0},
                       'battery_file': {'type': 'simple', 'key': 'STRING', 'value': 0},
                       # all uppercase keys are user set, so aren't actually "USER_SET"
                       'bluetooth_paired_whitelist': {'type': 'nested',
                                                      'outer_keys': {"USER_SET": 'STRING'},
                                                      'inner_keys': ['name', 'amount'],
                                                      'values': {'name': 'STRING', 'amount': 0}},
                       'bluetooth_connected_whitelist': {'type': 'nested',
                                                         'outer_keys': {"USER_SET": 'STRING'},
                                                         'inner_keys': ['name', 'amount'],
                                                         'values': {'name': 'STRING', 'amount': 0}}}
    list_info = {'email_destination': 'STRING'}
    config_variables = {"ac_file": ac_file, "usb_id_whitelist": usb_id_whitelist,
                        "usb_connected_whitelist": usb_connected_whitelist, "cdrom_drive": cdrom_drive,
                        "battery_file": battery_file, "ethernet_connected_file": ethernet_connected_file,
                        "bluetooth_paired_whitelist": bluetooth_paired_whitelist,
                        "bluetooth_connected_whitelist": bluetooth_connected_whitelist,
                        "smtp_server": smtp_server, "smtp_port": smtp_port, "email_sender": email_sender,
                        "email_destination": email_destination, "sender_password": sender_password,
                        "cipher_choice": cipher_choice, "login_auth": login_auth, "log_file": log_file}
    for variable in config_variables:
        # See if the variable is actually what we expect
        if isinstance(config_variables[variable], type(config_info[variable])):
            if isinstance(config_info[variable], dict):
                # a simple dict is a non-nested dict like a = {'b': 'c'}
                if dictionary_info[variable]['type'] == 'simple':
                    if dictionary_info[variable]['key'] == 'STRING':
                        if not isinstance(list(config_variables[variable].keys())[0], str):
                            item = list(config_variables[variable].keys())[0]
                            item_type = type(list(config_variables[variable].keys())[0])
                            print(f'{item} is of type {item_type} rather than the expected string')
                            config_good = False
                # nested dict is, well, a nested dict like a = {'b': {'c': 'd'}}
                elif dictionary_info[variable]['type'] == 'nested':
                    print('nested dict')
            elif isinstance(config_info[variable], list):
                print('list')
        else:
            variable_type = type(config_variables[variable])
            expected_type = config_info[variable]
            print(f'{variable} is of type {variable_type} rather than the expected {expected_type}')
            config_good = False
    if config_good is None:
        config_good = True
    if not config_good:
        print("The configuration file could not be verified.")
        sys.exit(1)

