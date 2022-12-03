import asyncio
import pyudev


usb_devices = {}
usb_ids = {}


async def get_usb():
    all_devicess = context.list_devices()
    print(all_devicess)
    all_devices = context.list_devices(subsystem='usb')
    for each_device in all_devices:
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


async def get_bluetooth():



async def main(monitor):
    for device in iter(monitor.poll, None):
        if device.get("ID_BUS") == "bluetooth":
            if device.get('PHYS') is not None:
                if device.action == 'add':
                    print('ADD - BLUETOOTH')
                    print(f"PHYS: {device.get('PHYS')} / {device.get('DEVPATH')}")
                elif device.action == 'remove':
                    print('REMOVE - BLUETOOTH')
                    print(f"PHYS: {device.get('PHYS')} / {device.get('DEVPATH')}")
        elif device.get("SUBSYSTEM") == "usb":
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


if __name__ == '__main__':
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(main(monitor))
