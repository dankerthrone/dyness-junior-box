#!/usr/bin/env python3
"""
Lokaler Mini-MQTT-Broker (anonym) fuer den Dyness-MITM-Versuch.
Empfaengt die Nachrichten, die der Collector sonst an logger.dyness.com:1883 sendet.
Laeuft mit dem Hermes-Standalone-Python:  python3 mqtt_broker.py  (> broker.log 2>&1)
Kein root noetig; Bind auf 0.0.0.0:1883 (im LAN erreichbar).
"""
import asyncio
import logging

from amqtt.broker import Broker

CONFIG = {
    "listeners": {
        "default": {"type": "tcp", "bind": "0.0.0.0:1883"},
    },
    "sys_interval": 10,
    # KEIN auth-Block: amqtt erlaubt anonym per Standard (AnonymousAuthPlugin,
    # allow_anonymous=True). Ein eigener auth-Block mit falschem Plugin-Namen
    # hat sonst ALLES abgelehnt (rc=5).
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-20s %(message)s",
)


async def main():
    broker = Broker(CONFIG)
    await broker.start()
    print("MQTT-Broker laeuft auf 0.0.0.0:1883 (anonym)", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())