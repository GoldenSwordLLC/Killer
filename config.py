# linux
ac_file = "/sys/class/power_supply/RUN_DEBUG"
usb_id_whitelist = {"DEAD:BEEF": 1}
usb_connected_whitelist = {"DEAD:BEEF": 1}
cdrom_drive = "/dev/sr0"
battery_file = "/sys/class/power_supply/RUN_DEBUG"
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
