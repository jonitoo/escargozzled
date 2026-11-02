import asyncio
import math
import os
import struct
from bleak import BleakScanner, BleakClient
from pynput.keyboard import Controller, Key

# --- BLE UUIDs ---
CYCLING_POWER_UUID = "00001818-0000-1000-8000-00805f9b34fb"
POWER_MEASUREMENT_UUID = "00002a63-0000-1000-8000-00805f9b34fb"

# Sterzo Smart GATT-UUIDs
STERZO_SERVICE_UUID = "347b0001-7635-408b-8918-8ff3949ce592"
STERZO_STEERING_UUID = "347b0030-7635-408b-8918-8ff3949ce592"
STERZO_CHALLENGE_UUID = "347b0031-7635-408b-8918-8ff3949ce592"
STERZO_INDICATE_UUID = "347b0032-7635-408b-8918-8ff3949ce592"
CHALLENGE_TABLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sterzo-challenge-codes.dat")

# --- Tuning ---
GAS_KEY = 'x'
MIN_WATT = 40
MAX_WATT = 280
STEER_DEADZONE_DEG = 3.0
STEER_MAX_DEG = 25.0

keyboard = Controller()
current_watts = 0
current_angle = 0.0
last_raw_hex = ""
running = True

def on_power_data(sender, data: bytearray):
    global current_watts
    _, power = struct.unpack_from("<Hh", data, 0)
    current_watts = max(0, power)

def on_steering_data(sender, data: bytearray):
    global current_angle, last_raw_hex
    last_raw_hex = data.hex()

    # Ignoriere Standard-Lock-Wert ffffffff
    if last_raw_hex.lower().startswith("ffffffff") or len(data) < 4:
        return

    # Little-Endian float32, Winkel bereits in Grad
    val = struct.unpack_from("<f", data, 0)[0]
    if not math.isnan(val):
        current_angle = val

def calculate_challenge_response(challenge: int) -> bytearray:
    # Lookup-Tabelle (65536 x 2 Bytes) aus pycycling (MIT), Index = Challenge (Big-Endian)
    with open(CHALLENGE_TABLE_FILE, "rb") as f:
        f.seek(challenge * 2)
        code = f.read(2)
    return bytearray([0x03, 0x11, code[0], code[1]])

async def authenticate_sterzo(client: BleakClient) -> bool:
    print("🔐 Authentifiziere Sterzo Smart...")
    challenge_received = asyncio.Event()
    challenge_value = None

    def indicate_callback(sender, data: bytearray):
        nonlocal challenge_value
        print(f" -> Sterzo Indication: {data.hex()}")
        if len(data) >= 4 and data[0] == 0x03 and data[1] == 0x10:
            challenge_value = int.from_bytes(data[2:4], "big")
            challenge_received.set()

    # Beide Characteristics abonnieren, BEVOR die Challenge angefordert wird
    await client.start_notify(STERZO_INDICATE_UUID, indicate_callback)
    await client.start_notify(STERZO_STEERING_UUID, on_steering_data)
    await asyncio.sleep(0.5)

    for attempt in range(1, 4):
        print(f" -> Fordere Challenge an [0310] (Versuch {attempt})...")
        await client.write_gatt_char(STERZO_CHALLENGE_UUID, bytearray([0x03, 0x10]), response=True)
        try:
            await asyncio.wait_for(challenge_received.wait(), timeout=5.0)
            break
        except asyncio.TimeoutError:
            print("    keine Challenge erhalten.")
    else:
        print("❌ Sterzo hat keine Challenge gesendet.")
        return False

    response_packet = calculate_challenge_response(challenge_value)
    print(f" -> Challenge {challenge_value:#06x}, sende Antwort {response_packet.hex()}")
    await client.write_gatt_char(STERZO_CHALLENGE_UUID, response_packet, response=True)
    await asyncio.sleep(1.0)

    print(" -> Aktiviere Lenkwinkel-Messung [0202]")
    await client.write_gatt_char(STERZO_CHALLENGE_UUID, bytearray([0x02, 0x02]), response=True)
    return True

async def game_input_loop():
    global current_watts, current_angle, running, last_raw_hex

    is_left = False
    is_right = False
    cycle_time = 0.05

    while running:
        # Lenkung nur verarbeiten, wenn echte Winkel vorliegen (nicht gelockt)
        if not last_raw_hex.lower().startswith("ffffffff") and last_raw_hex != "":
            if current_angle < -STEER_DEADZONE_DEG:
                if not is_left:
                    keyboard.press(Key.left)
                    is_left = True
                if is_right:
                    keyboard.release(Key.right)
                    is_right = False
            elif current_angle > STEER_DEADZONE_DEG:
                if not is_right:
                    keyboard.press(Key.right)
                    is_right = True
                if is_left:
                    keyboard.release(Key.left)
                    is_left = False
            else:
                if is_left:
                    keyboard.release(Key.left)
                    is_left = False
                if is_right:
                    keyboard.release(Key.right)
                    is_right = False
        else:
            if is_left:
                keyboard.release(Key.left)
                is_left = False
            if is_right:
                keyboard.release(Key.right)
                is_right = False

        # Gas (PWM über Watt)
        duty = 0.0
        if current_watts >= MIN_WATT:
            duty = min(1.0, max(0.0, (current_watts - MIN_WATT) / (MAX_WATT - MIN_WATT)))

        if duty <= 0:
            keyboard.release(GAS_KEY)
            await asyncio.sleep(cycle_time)
        elif duty >= 1.0:
            keyboard.press(GAS_KEY)
            await asyncio.sleep(cycle_time)
        else:
            p_time = cycle_time * duty
            r_time = cycle_time * (1.0 - duty)
            keyboard.press(GAS_KEY)
            await asyncio.sleep(p_time)
            keyboard.release(GAS_KEY)
            await asyncio.sleep(r_time)

        status = f"{current_angle:+5.1f}°" if (not last_raw_hex.lower().startswith("ffffffff") and last_raw_hex != "") else "GESPERRT"
        print(f"\r[Avanti: {current_watts:3d} W] [Sterzo: {status} | Hex: {last_raw_hex}] Gas: {int(duty * 100):3d}%", end="")

async def main():
    print("Suche Elite Avanti und Sterzo Smart...")
    discovered = await BleakScanner.discover(return_adv=True, timeout=6.0)

    trainer_dev = None
    sterzo_dev = None

    for address, (device, adv) in discovered.items():
        name = (device.name or "").upper()
        services = [s.lower() for s in (adv.service_uuids or [])]

        if "STERZO" in name and "ARIA" not in name:
            sterzo_dev = device
            print(f" -> Sterzo: {device.name}")
        elif "AVANTI" in name or CYCLING_POWER_UUID.lower() in services:
            trainer_dev = device
            print(f" -> Avanti: {device.name}")

    if not trainer_dev or not sterzo_dev:
        print("Geräte nicht vollständig gefunden.")
        return

    print(f"\nVerbinde mit {trainer_dev.name} und {sterzo_dev.name}...")
    async with BleakClient(trainer_dev) as trainer_client, BleakClient(sterzo_dev) as sterzo_client:
        await authenticate_sterzo(sterzo_client)
        await trainer_client.start_notify(POWER_MEASUREMENT_UUID, on_power_data)

        print("\n🔥 Verbunden! Bewege jetzt den Lenker.\n")
        await game_input_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        running = False
        keyboard.release(GAS_KEY)
        keyboard.release(Key.left)
        keyboard.release(Key.right)
        print("\nBeendet.")