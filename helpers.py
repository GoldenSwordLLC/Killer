import fcntl
import json
import logging
import os
import re
import smtplib
import socket
import ssl
import subprocess
import time
from email.mime.text import MIMEText
from pathlib import Path
from config import ac_file, usb_id_whitelist, usb_connected_whitelist, cdrom_drive, battery_file
from config import ethernet_connected_file, bluetooth_paired_whitelist, bluetooth_connected_whitelist, smtp_server
from config import smtp_port, sender, destination, sender_password, cipher_choice, login_auth
from config import log_file, debug_enable

log = logging.getLogger('Base')

CONFIG_SEARCH_PATHS = [Path.cwd(), Path.home()]
CONFIG_FILENAME = "config.py"

BT_MAC_REGEX = re.compile(r"(?:[0-9a-fA-F]:?){12}")
BT_PAIRED_REGEX = re.compile(r"(Paired: [0-1])")
BT_NAME_REGEX = re.compile(r"[0-9A-Za-z ]+(?=\s\()")
BT_CONNECTED_REGEX = re.compile(r"(Connected: [0-1])")
USB_ID_REGEX = re.compile(r"([0-9a-fA-F]{4}:[0-9a-fA-F]{4})")

POWER_PATH = Path('/sys/class/power_supply')
POWER_DEVICE_TYPES = ['Battery', 'Mains', 'UPS', 'USB']

LOG = logging.getLogger('POSIX')

if debug_enable:
    DEBUG = True
else:
    DEBUG = False


def detect_bt():
    try:
        bt_command = subprocess.check_output(["bt-device", "--list"],
                                             shell=False).decode()
    except Exception as e:
        log.debug('Bluetooth: none detected (exception: {0})'.format(e))
    else:
        if DEBUG:
            # TODO: Clean up
            bt_devices = bt_command.split('\n')
            if len(bt_devices) == 3 and bt_devices[2] == '':
                log.debug('Bluetooth:', bt_command.split('\n')[1])
            else:
                log.debug('Bluetooth:', ', '.join(bt_command.split('\n')[1:]))
        else:
            paired_devices = re.findall(BT_MAC_REGEX, bt_command)
            devices_names = re.findall(BT_NAME_REGEX, bt_command)
            for each in range(0, len(paired_devices)):
                if paired_devices[each] not in bluetooth_paired_whitelist:
                    kill_the_system('Bluetooth Paired: {0}'.format(paired_devices[each]))
                else:
                    connected = subprocess.check_output(
                        ["bt-device", "-i",
                         paired_devices[each]],
                        shell=False).decode()
                    connected_text = re.findall(BT_CONNECTED_REGEX, connected)
                    if connected_text[0].endswith("1") \
                            and paired_devices[each] not in bluetooth_connected_whitelist:
                        kill_the_system('Bluetooth Connected MAC Disallowed: {0}'.format(paired_devices[each]))
                    elif connected_text[0].endswith("1") and each in bluetooth_connected_whitelist:
                        # TODO - This is wrong and needs fixed up
                        if devices_names[each] != bluetooth_paired_whitelist[]:
                            kill_the_system('Bluetooth Connected Name Mismatch: {0}'.format(devices_names[each]))


def detect_usb():
    ids = re.findall(USB_ID_REGEX, subprocess.check_output("lsusb", shell=False).decode())
    if ids:
        log.debug('USB:', ', '.join(ids))
    else:
        log.debug('USB: none detected')

    for each_device in ids:
        if each_device not in usb_id_whitelist:
            kill_the_system('USB Allowed Whitelist: {0}'.format(each_device))
        else:
            if usb_id_whitelist[each_device] != ids.count(each_device):
                kill_the_system('USB Duplicate Device: {0}'.format(each_device))

    for device in usb_connected_whitelist:
        if device not in ids:
            kill_the_system('USB Connected Whitelist: {0}'.format(device))


def detect_ac():
    if DEBUG:
        devices = ', '.join(power.get_devices(power.DeviceType.MAINS))
        log.debug('AC:', devices if devices else 'none detected')

    if not power.is_online(config['linux']['ac_file']):
        kill_the_system('AC')


def detect_battery():
    if DEBUG:
        devices = ', '.join(power.get_devices(power.DeviceType.BATTERY))
        log.debug('Battery:', devices if devices else 'none detected')

    try:
        if not power.is_present(config['linux']['battery_file']):
            kill_the_system('Battery')
    except FileNotFoundError:
        pass


def detect_tray():
    disk_tray = cdrom_drive
    fd = os.open(disk_tray, os.O_RDONLY | os.O_NONBLOCK)
    rv = fcntl.ioctl(fd, 0x5326)
    os.close(fd)

    log.debug('CD Tray:', rv)

    if rv != 1:
        kill_the_system('CD Tray')


def detect_ethernet():
    with open(ethernet_connected_file) as ethernet:
        connected = int(ethernet.readline().strip())

    log.debug('Ethernet:', connected)

    if connected:
        kill_the_system('Ethernet')


def kill_the_system(warning: str):
    """Send an e-mail, and then
    shut the system down quickly.
    """
    log.critical('Kill reason: ' + warning)
    if DEBUG:
        return
    try:
        mail_this(warning)
    except socket.gaierror:
        current_time = time.localtime()
        formatted_time = time.strftime('%Y-%m-%d %I:%M:%S%p', current_time)
        with open(log_file, 'a', encoding='utf-8') as the_log_file:
            the_log_file.write('Time: {0}\nInternet is out.\n'
                              'Failure: {1}\n\n'.format(formatted_time, warning))
    if not DEBUG:
        subprocess.Popen(["/sbin/poweroff", "-f"])


# TODO - Get Jinja templating setup for this
def mail_this(warning: str):
    email_config = config["email"]
    subject = '[ALERT: {0}]'.format(warning)

    current_time = time.localtime()
    formatted_time = time.strftime('%Y-%m-%d %I:%M:%S%p', current_time)

    content = 'Time: {0}\nWarning: {1}'.format(formatted_time, warning)
    msg = MIMEText(content, 'plain')
    msg['Subject'] = subject
    msg['From'] = email_config["sender"]
    ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.set_ciphers(email_config["cipher_choice"])
    ssl_context.options |= ssl.HAS_SNI
    ssl_context.options |= ssl.OP_NO_COMPRESSION
    # No need to explicitly disable SSLv* as it's already been done
    # https://docs.python.org/3/library/ssl.html#id7
    ssl_context.options |= ssl.OP_NO_TLSv1
    ssl_context.options |= ssl.OP_NO_TLSv1_1
    ssl_context.options |= ssl.OP_SINGLE_DH_USE
    ssl_context.options |= ssl.OP_SINGLE_ECDH_USE
    conn = smtplib.SMTP_SSL(email_config["smtp_server"],
                            port=email_config["smtp_port"],
                            context=ssl_context)
    conn.esmtp_features['auth'] = email_config["login_auth"]
    conn.login(email_config["sender"], email_config["sender_password"])
    try:
        for each in json.loads(email_config["destination"]):
            conn.sendmail(email_config["sender"], each, msg.as_string())
    except socket.timeout:
        raise socket.gaierror
    finally:
        conn.quit()


def read_power_devices():
    temp_dict = {}
    for item in POWER_PATH.iterdir():
        filename = item.name
        temp_dict[filename] = {}
        # The uevent file actually has everything we want in one file.
        # Name, status, and type. No reason to load several files when one has all of this.
        device_uevent = Path(item, 'uevent')
        if os.path.isfile(device_uevent):
            with open(device_uevent, 'r') as power_file:
                lines = power_file.readlines()
            for line in lines:
                stripped_line = line.strip().replace('POWER_SUPPLY_', '')
                if stripped_line.startswith('TYPE'):
                    temp_dict[filename]['type'] = stripped_line.replace('TYPE=', '')
                elif stripped_line.startswith('ONLINE'):
                    temp_dict[filename]['online'] = stripped_line.replace('ONLINE=', '')
    print(temp_dict)


def read_power_folder():
    for item in POWER_PATH.iterdir():
        print(time.ctime(item))
