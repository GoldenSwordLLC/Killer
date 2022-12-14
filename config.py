#!/usr/bin/env python3
# If you choose to not use any of these, ensure they're empty ( set to {} ) rather than removed.


# -- Power --
# 1 defines present, 0 defines not present
ac_file = {'AC': 1}
# 1 defines present, 0 defines not present
battery_file = {'BAT1': 1}


# -- USB --
usb_id_whitelist = {"DEAD:BEEF": 1}
usb_connected_whitelist = {"DEAD:BEEF": 1}


# -- Disk tray --
# 1 = no disk
# 2 = tray open
# 3 = reading tray
# 4 = disk, tray closed
cdrom_drive = {"/dev/sr0": 1}


# -- Network --
# 1 defines present, 0 defines not present
ethernet_connected_file = {"/sys/class/net/RUN_DEBUG/carrier": 1}
# TODO: Add wifi here


# -- Bluetooth --
# Devices that need to be paired. These can be removed/connected.
bluetooth_paired_whitelist = {"DE:AD:BE:EF:CA:FE": {"name": "Generic Bluetooth Device", "amount": 1},
                              "AB:CD:EF:12:34:56": {"name": "Generic Bluetooth Device 2", "amount": 1}}
# Devices that need to be connected at all times and being removed is considered tampering.
bluetooth_connected_whitelist = {"DE:AD:BE:EF:CA:FE": {"name": "Generic Bluetooth Device", "amount": 1},
                                 "AB:CD:EF:12:34:56": {"name": "Generic Bluetooth Device 2", "amount": 1}}


# -- E-mail --
smtp_server = "mail.example.com"
smtp_port = 465
email_sender = "example@example.com"
email_destination = ["example@example.com", "example2@example.com"]
sender_password = "V%gË¼Ïã4pÖtÜãQP;ëÇRÂ«!òeH2øÀbxZ¡ÅT8¿Cï*ðrøkÝ*åÐA]¥R/XZ'¢"
cipher_choice = "ECDHE-RSA-AES256-GCM-SHA384"
login_auth = "LOGIN"
# TODO: This may be too low, experiment with this
email_timeout = 0.8


# -- Logging --
# Change this if you want to actually log anything
log_file = "/something/something.txt"


# -- Debug --
debug_enabled = True


# -- Enabling --
bluetooth_enabled = True
email_enabled = True
logging_enabled = True
usb_enabled = True


# -- Time --
# Check /usr/share/zoneinfo for options here. Some examples would be:
# "Europe/Paris", "US/Pacific", "Asia/Singapore", "Brazil/West"
user_timezone = "US/Eastern"
# Formatting. https://docs.python.org/3/library/time.html#time.strftime has the options for this
# By default this looks like 2022-12-31 01:59:59PM
time_format = "%Y-%m-%d %I:%M:%S%p"
