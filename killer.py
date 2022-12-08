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
from config import bluetooth_enabled, cipher_choice, debug_enabled, email_destination, email_enabled, email_sender
from config import log_file, logging_enabled, login_auth, smtp_server, smtp_port, sender_password, time_format
from config import usb_enabled, user_timezone

BT_MAC_REGEX = re.compile(r"(?:[0-9a-fA-F]:?){12}")
BT_NAME_REGEX = re.compile(r"[0-9A-Za-z ]+(?=\s\()")
BT_CONNECTED_REGEX = re.compile(r"(Connected: [0-1])")
usb_devices = {}
usb_ids = {}


# Root is required for shutting down unless you allow your user to
# shut the system down, which isn't recommended.
async def detect_root():
    if getpass.getuser() == 'root':
        return True
    else:
        return False


# TODO: This doesn't currently handle systems with more than one physical volume
async def check_for_luks():
    physical_volumes = subprocess.check_output(['pvs', '-o', 'pv_name']).decode().split('\n')[1:-1]
    for physical_volume in physical_volumes:
        physical_volume = physical_volume.strip()
        cryptsetup_status = subprocess.check_output(['cryptsetup', 'status', physical_volume]).decode().split('\n')
        _, encryption_type = cryptsetup_status[1].split()
        if encryption_type == 'LUKS2':
            if len(physical_volumes) == 1:
                return True
    return None


async def set_time_settings():
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
            print('ADD - BLUETOOTH')
            await get_all_bluetooth()
        elif this_device.action == 'remove':
            print('REMOVE - BLUETOOTH')
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


async def tampering_detected(warning: str):
    await custom_tampering_command(warning)


# Run whatever you want here if tampering is detected.
# By default, if all the options are enabled for e-mail/logging AND debugging isn't enabled this will:
# send an e-mail out, log to disk, and shut the system off
async def custom_tampering_command(warning: str):
    # TODO
    socket_error = False
    if email_enabled:
        try:
            await mail_this(warning)
        except socket.gaierror:
            # TODO
            socket_error = True
    if logging_enabled:
        current_time = time.localtime()
        formatted_time = time.strftime(time_format, current_time)
        try:
            with open(log_file, 'a', encoding='utf-8') as the_log_file:
                the_log_file.write('Time: {0}\nInternet is out.\n'
                                   'Failure: {1}\n\n'.format(formatted_time, warning))
        except FileNotFoundError:
            if debug_enabled:
                print(f'Tampering detected: {log_file} is not a valid file.')
            else:
                pass
    if not debug_enabled:
        subprocess.Popen(["/sbin/poweroff", "-f"])


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


if __name__ == '__main__':
    running_as_root = detect_root()
    if not running_as_root:
        sys.exit(1)
    is_encrypted = check_for_luks()
    if not is_encrypted:
        sys.exit(1)
    set_time_settings()
    get_all_usb()
    get_all_bluetooth()
    context = pyudev.Context()
    pyudev_monitor = pyudev.Monitor.from_netlink(context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(main(pyudev_monitor))
