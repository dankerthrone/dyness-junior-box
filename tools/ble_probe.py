#!/usr/bin/env python3
"""
Dyness Junior Box — BLE-Probe (Phase 3, Ent-Clouden)
GATT: Service FE00 (FE01 Write, FE02 Notify, FED5 Write-Init, FED6 Indicate)
      + unbekannter Service e31c42f9-... (Write+Indicate, evtl. Kommando-Kanal)
JBD-Framing: dd a5 03 00 ff fd 77 = Basic Info, 04 = Zellspannungen, 05 = Gerätename
Aufruf: ble_probe.py [--mtu] [--unknown]   (beide Flags aktivieren die Zusatzproben)
"""
import asyncio
import sys
import binascii

from bleak import BleakClient

ADDR = "XX:XX:XX:XX:XX:XX"
UUID_FE01 = "0000fe01-0000-1000-8000-00805f9b34fb"
UUID_FE02 = "0000fe02-0000-1000-8000-00805f9b34fb"
UUID_FED5 = "0000fed5-0000-1000-8000-00805f9b34fb"
UUID_FED6 = "0000fed6-0000-1000-8000-00805f9b34fb"
UUID_UNK  = "e31c42f9-dd47-45bf-81eb-2b735d61365a"   # unbekannter Write/Indicate-Kanal

INIT      = bytearray.fromhex("aa5501000056")
JBD_CMDS  = {
    "basic_info": bytearray.fromhex("dda50300fffd77"),
    "cell_volts": bytearray.fromhex("dda50400fffc77"),
    "dev_name":   bytearray.fromhex("dda50500fffb77"),
}
notified = []

def on_notify(_c, data): notified.append(("FE02", bytes(data)))
def on_indicate(_c, data): notified.append(("FED6", bytes(data)))
def on_unk(_c, data): notified.append(("UNK", bytes(data)))

async def try_mtu(client):
    try:
        await client._backend._acquire_mtu()
        print(f"MTU nach _acquire_mtu(): {client.mtu_size}")
        return client.mtu_size
    except Exception as e:
        print(f"MTU-Erhöhung fehlgeschlagen: {e}")
        return None

async def main():
    do_mtu = "--mtu" in sys.argv
    do_unk = "--unknown" in sys.argv

    print(f"Verbinde {ADDR} ...")
    async with BleakClient(ADDR, timeout=20) as client:
        print(f"verbunden: {client.is_connected} | MTU: {client.mtu_size}")
        if do_mtu:
            await try_mtu(client)

        await client.start_notify(UUID_FE02, on_notify)
        try:
            await client.start_notify(UUID_FED6, on_indicate)
        except Exception as e:
            print(f"(FED6 nicht abonnierbar: {e})")
        if do_unk:
            try:
                await client.start_notify(UUID_UNK, on_unk)
                print(f"UNK {UUID_UNK} abonniert")
            except Exception as e:
                print(f"(UNK nicht abonnierbar: {e})")

        target_writes = [(UUID_FED5, INIT, "Init FED5")]
        for name, cmd in JBD_CMDS.items():
            target_writes.append((UUID_FE01, cmd, f"JBD {name} FE01"))
        if do_unk:
            target_writes.append((UUID_UNK, INIT, "Init -> UNK"))
            target_writes.append((UUID_UNK, JBD_CMDS["basic_info"], "JBD basic -> UNK"))

        for uuid, payload, label in target_writes:
            print(f"-- {label}: {payload.hex()} --")
            try:
                await client.write_gatt_char(uuid, payload, response=False)
            except Exception as e:
                print(f"   FEHLER: {e}")
            await asyncio.sleep(1.5)

        print("\n-- Warte auf Antworten (10s) --")
        await asyncio.sleep(10)
        for uuid in (UUID_FE02, UUID_FED6, UUID_UNK):
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass

        if notified:
            print(f"\n{len(notified)} Antwort(en):")
            for ch, data in notified:
                print(f"  {ch}: {binascii.hexlify(data).decode()}  ({data})")
        else:
            print("\nKEINE Antworten (Init+JBD an FE01/UNK; MTU-Probe). Session-Handshake weiter offen.")

asyncio.run(main())