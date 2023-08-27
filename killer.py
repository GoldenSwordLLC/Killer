import argparse
import asyncio
import getpass
import os
import re
import smtplib
import socket
import ssl
import subprocess
import sys
import time
from email.mime.text import MIMEText
import pyudev

VERSION = "0.8.3"
BT_MAC_REGEX = re.compile(r"(?:[0-9a-fA-F]:?){12}")
BT_NAME_REGEX = re.compile(r"[0-9A-Za-z ]+(?=\s\()")
BT_CONNECTED_REGEX = re.compile(r"(Connected: [0-1])")
usb_devices = {}
usb_ids = {}

# TODO - This actually needs used.
#  If someone specifies a config and it's unavailable/mangled..
#  then we need somewhere to get the config. This is that place.
default_config = {'ac_file': {'AC': 1},
                  'battery_file': {'BAT1': 1},
                  'usb_id_allowlist': {"DEAD:BEEF": 1},
                  'usb_connected_whitelist': {"DEAD:BEEF": 1},
                  'cdrom_drive': {"/dev/sr0": 1},
                  'ethernet_connected_file': {r"/sys/class/net/RUN_DEBUG/carrier": 1},
                  'bluetooth_paired_allowlist': {"DE:AD:BE:EF:CA:FE": {"name": "Generic Bluetooth Device", "amount": 1},
                                                 "AB:CD:EF:12:34:56": {"name": "Generic Bluetooth Device 2", "amount": 1}},
                  'bluetooth_connected_allowlist': {"DE:AD:BE:EF:CA:FE": {"name": "Generic Bluetooth Device", "amount": 1},
                                                    "AB:CD:EF:12:34:56": {"name": "Generic Bluetooth Device 2", "amount": 1}},
                  'smtp_server': "mail.example.com",
                  'smtp_port': 465,
                  'email_sender': "example@example.com",
                  'email_destination': ["example@example.com", "example2@example.com"],
                  'sender_password': "9b§ì]QîiT{¹5¡/ã¦¥µ+På\yµ'¾SéÉA¸^f|BóÚ{PÙóÕm,öÞÇÙú>:ûK65ÏNö¿^Z8bs",
                  'cipher_choice': "ECDHE-RSA-AES256-GCM-SHA384",
                  'login_auth': "LOGIN",
                  'email_timeout': 0.8,
                  'log_file': "/something/something.txt",
                  'debug_enabled': True,
                  'bluetooth_enabled': True,
                  'email_enabled': True,
                  'logging_enabled': True,
                  'usb_enabled': True,
                  'user_timezone': "US/Eastern",
                  'time_format': "%Y-%m-%d %I:%M:%S%p"}



# Root is required for shutting down unless you allow your user to
# shut the system down, which isn't recommended.
async def detect_root_user() -> bool:
    if getpass.getuser() == 'root':
        return True
    else:
        return False


async def pv_encrypted(the_pv) -> bool:
    cryptsetup_status = subprocess.check_output(['cryptsetup', 'status', the_pv]).decode().split('\n')
    _, encryption_type = cryptsetup_status[1].split()
    if encryption_type == 'LUKS2':
        return True
    else:
        return False


async def check_for_luks() -> bool:
    pv_list = []
    physical_volumes = subprocess.check_output(['pvs', '-o', 'pv_name']).decode().split()[1:]
    for pv in physical_volumes:
        if pv not in pv_list:
            pv_list.append(pv)
    if len(pv_list) == 1:
        if await pv_encrypted(pv_list[0]):
            return True
        else:
            return False
    else:
        for the_physical_volume in pv_list:
            if not await pv_encrypted(the_physical_volume):
                return False
        return True


async def set_time_settings():
    if debug_set:
        print(f"DEBUG: Your timezone would have been set to `{user_timezone}`")
    else:
        os.environ['TZ'] = user_timezone
        time.tzset()


# Bluetooth on Ubuntu 22.04 LTS ( and possibly others ) will only provide the adapter MAC via dbus.
# So, this function happens any time there's an add or remove action.
# This really isn't the preferred way of doing this, and it'd be nice to just have dbus handling this.
async def get_all_bluetooth():
    # TODO
    bluetooth_devices = None
    try:
        bluetooth_devices_command = subprocess.check_output(["bt-device", "--list"], shell=False).decode()
    except Exception as e:
        print('Bluetooth: Exception: {0})'.format(e))
    else:
        if bluetooth_devices_command != "No devices found":
            paired_devices = re.findall(BT_MAC_REGEX, bluetooth_devices_command)
            device_names = re.findall(BT_NAME_REGEX, bluetooth_devices_command)
            print(paired_devices)
            print(device_names)


async def get_all_usb():
    all_usb_devices = context.list_devices(subsystem='usb')
    for each_device in all_usb_devices:
        if each_device.device_node is not None:
            this_device = each_device.get('DEVPATH')
            device_ids = f"{each_device.get('ID_VENDOR_ID')}{each_device.get('ID_MODEL_ID')}"
            if device_ids in usb_ids:
                usb_ids[device_ids] += 1
            else:
                usb_ids[device_ids] = 1
            if this_device in usb_devices:
                usb_devices[this_device]['amount'] += 1
            else:
                usb_devices[this_device] = {}
                usb_devices[this_device]['amount'] = 1
                usb_devices[this_device]['ids'] = f"{each_device.get('ID_VENDOR_ID')}:{each_device.get('ID_MODEL_ID')}"
    print(usb_devices)
    print(usb_ids)


async def handle_bluetooth(this_device):
    if this_device.get('PHYS') is not None:
        if this_device.action == 'add':
            if debug_enabled:
                print('DEBUG: Bluetooth - device added')
            await get_all_bluetooth()
        elif this_device.action == 'remove':
            if debug_enabled:
                print('DEBUG: Bluetooth - device removed')
            await get_all_bluetooth()


# TODO - Get Jinja templating setup for this
async def mail_this(warning: str):
    subject = f'[Killer: {warning}]'

    current_time = time.localtime(user_timezone)
    formatted_time = time.strftime(time_format, current_time)

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
                            context=ssl_context,
                            timeout=email_timeout)
    conn.esmtp_features['auth'] = login_auth
    conn.login(email_sender, sender_password)
    try:
        for each in email_destination:
            conn.sendmail(email_sender, each, msg.as_string())
    except socket.timeout:
        raise socket.gaierror
    finally:
        conn.quit()


async def tampering_detected(warning: str):
    await default_tampering_command(warning)
    # await custom_tampering_command(warning)


# By default, if all the options are enabled for e-mail/logging AND debugging isn't enabled this will:
# send an e-mail out, log to disk, and force shutdown the system
async def default_tampering_command(warning: str):
    if not debug_set:
        socket_error = False
        if email_enabled:
            try:
                await mail_this(warning)
            except socket.gaierror:
                socket_error = True
        if logging_enabled:
            current_time = time.localtime()
            formatted_time = time.strftime(time_format, current_time)
            try:
                if socket_error:
                    with open(log_file, 'a', encoding='utf-8') as the_log_file:
                        the_log_file.write(f'Time: {formatted_time}\nE-mail attempt failed.\nFailure: {warning}\nShutting down now.\n\n')
                else:
                    with open(log_file, 'a', encoding='utf-8') as the_log_file:
                        the_log_file.write(f'Time: {formatted_time}\nFailure: {warning}\nShutting down now.\n\n')
            except(FileNotFoundError, PermissionError):
                # Debugging is disabled. We tried to log, but it failed for some reason.
                # Can't really do anything here, so just pass.
                pass
        subprocess.Popen(["/sbin/poweroff", "-f"])
    else:
        if email_enabled:
            if logging_enabled:
                print("DEBUG: E-mail, logging, and shutdown were not triggered")
            else:
                print("DEBUG: E-mail and shutdown were not triggered")
        else:
            if logging_enabled:
                print("DEBUG: Logging and shutdown were not triggered")
            else:
                print("DEBUG: Shutdown was not triggered")



# Run whatever you want here if tampering is detected.
# If you set anything here, also change the tampering_detected function to actually run this.
async def custom_tampering_command(warning: str):
    pass


async def main(monitor):
    for device in iter(monitor.poll, None):
        if device.get("ID_BUS") == "bluetooth":
            if bluetooth_enabled:
                await handle_bluetooth(device)
        elif device.get("SUBSYSTEM") == "usb":
            if usb_enabled:
                the_devpath = device.get('DEVPATH')
                device_ids = f"{device.get('ID_VENDOR_ID')}:{device.get('ID_MODEL_ID')}"
                if device.get('ID_VENDOR_ID') is not None and device.get('ID_MODEL_ID') is not None:
                    if device.action == 'add':
                        print('ADD - USB')
                        usb_devices[the_devpath] = device_ids
                        print(device_ids)
                    elif device.action == 'bind':
                        print('BIND - USB')
                        print(device_ids)
                    elif device.action == 'change':
                        print('CHANGE - USB')
                        print(device_ids)
                if device.action == 'remove':
                    if device.get('DEVPATH') in usb_devices:
                        print('REMOVE - USB')
                        these_ids = usb_devices[the_devpath]['ids']
                        usb_devices.pop(the_devpath)
                        print(f"{these_ids} popped!")
        elif device.get('SUBSYSTEM') == "power_supply":
            if device.action == 'change':
                print('CHANGE - POWER')
                print(f"{device.get('POWER_SUPPLY_NAME')}")
                print(f"{device.get('POWER_SUPPLY_TYPE')}")
                print(f"{device.get('POWER_SUPPLY_ONLINE')}")
        elif device.get("SUBSYSTEM") == "net":
            print("ethernet")
        elif device.get("SUBSYSTEM") == "rfkill":
            if device.get("RFKILL_TYPE") == "wlan":
                print(f'{device.get("RFKILL_NAME")} / {device.get("RFKILL_STATE")}')
        # This is used via HDMI
        elif device.get("SUBSYSTEM") == "drm":
            print("TODO")
        # Heat and periodic thermal updates
        elif device.get("SUBSYSTEM") == "thermal":
            print("TODO")


def the_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="Killer")
    parser.add_argument("-v", "--version", action="version",
                        version="%(prog)s {}".format(VERSION))
    # TODO - The different flavors of debug need to actually do what they advertise
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Debug. Prints all info once, without worrying about shutdown.")
    parser.add_argument("-di", "--debug-interactive", action="store_true",
                        help="Debug, interactive." +
                             "Prints all info once, without worrying about shutdown, " +
                             "AND stores what was detected interactively.")
    # TODO - This isn't actually paid attention to, change this.
    parser.add_argument("-c", "--config", type=str, default=None,
                        help="Path to a configuration file to use")
    # TODO - This isn't actually paid attention to, change this.
    parser.add_argument("-lc", "--log-config", type=str, default=None,
                        help="Path to logging configuration file.")
    parser.add_argument("-e", "--email", action="store_true",
                        help="Whether e-mail is enabled or not if tampering is detected.")
    # TODO - Add something that enables/disables local time being set for e-mail/logs
    all_args = parser.parse_args()
    return all_args


def verify_custom_config(the_config):
    if os.path.isfile(args.config):
        with open(the_config, 'r') as config_file:
            the_file = config_file.readlines()
            # TODO - Continue verification of custom config here.
    else:
        return None


if __name__ == '__main__':
    debug_set = False
    args = the_args()
    # TODO - Check if debuginteractive is right
    if any([args.debug, args.debuginteractive]):
        debug_set = True
    if args.config:
        # TODO - actually iterate through all enabled configurations via argparse for this.
        #  Also verify the file itself to ensure there isn't anything extra, and that the
        #  format is done in a way that is expected.
        config = args.config
        if args.email:
            from config import cipher_choice, email_destination, email_enabled, email_sender, email_timeout
            from config import login_auth, smtp_server, smtp_port, sender_password
        if args.bluetooth:
            from config import bluetooth_enabled
    else:
        # TODO - handle loading the default config file. If that doesn't exist..
        #  then load defaults from default_config up above.
        # TODO - These configs need moved somewhere else for their specific items.
        from config import debug_enabled, time_format, usb_enabled, user_timezone
        from config import log_file, logging_enabled
    running_as_root = detect_root_user()
    if not running_as_root:
        if debug_set:
            print("DEBUG: You're not running as root")
        else:
            sys.exit(1)
    is_encrypted = check_for_luks()
    if not is_encrypted:
        if debug_set:
            print("DEBUG: This system is not encrypted with LUKS")
        else:
            sys.exit(1)
    # TODO - Check if time settings is enabled/disabled. Fall back to UTC if disabled.
    # Set time for mail
    set_time_settings()
    # TODO - Check if USB devices are enabled/disabled
    # Get all current USB devices
    get_all_usb()
    # TODO - Check if Bluetooth devices are enabled/disabled
    # Get all current Bluetooth devices
    get_all_bluetooth()
    if not debug_set:
        context = pyudev.Context()
        pyudev_monitor = pyudev.Monitor.from_netlink(context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        asyncio.run(main(pyudev_monitor))
