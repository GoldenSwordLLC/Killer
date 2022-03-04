# If you choose to not use any of these, ensure they're empty rather than removed.
# This is because verify_config() within helpers.py will look for these.
# Unused strings should be "", lists should be [], dictionaries should be {}.
# Also make sure you edit checks() within killer.py to remove the checks you don't care for.

# 1 defines present, 0 defines not present
ac_file = {'AC': 1}
usb_id_whitelist = {"DEAD:BEEF": 1}
usb_connected_whitelist = {"DEAD:BEEF": 1}
cdrom_drive = "/dev/sr0"
# 1 defines present, 0 defines not present
battery_file = {'BAT1': 1}
ethernet_connected_file = "/sys/class/net/RUN_DEBUG/carrier"

# bluetooth
bluetooth_paired_whitelist = {"DE:AD:BE:EF:CA:FE": {"name": "Generic Bluetooth Device", "amount": 1}}
bluetooth_connected_whitelist = {"DE:AD:BE:EF:CA:FE": {"name": "Generic Bluetooth Device", "amount": 1}}

# e-mail
smtp_server = "mail.example.com"
smtp_port = 465
email_sender = "example@example.com"
email_destination = ["example@example.com", "example2@example.com"]
sender_password = "s0m3p4$$W0rD"
cipher_choice = "ECDHE-RSA-AES256-GCM-SHA384"
login_auth = "LOGIN"

sleep_length = 1.0
log_file = "/something/something.txt"
debug_enable = 1
