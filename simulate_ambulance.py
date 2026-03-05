import sys
import asyncio
import socketio
import numpy as np

SERVER_URL = "http://localhost:8000"

async def simulate(emergency_id):
    sio = socketio.AsyncClient()
    
    try:
        await sio.connect(SERVER_URL)
        print(f"Connected to AURA server")
        print(f"Simulating ambulance for: {emergency_id}")
        print(f"Starting simulation...")
        print()
    except Exception as e:
        print(f"Cannot connect: {e}")
        print(f"Make sure server is running:")
        print(f"uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        return

    start_lat, start_lng = 11.0200, 11.9600
    end_lat,   end_lng   = 11.0168, 76.9558
    steps = 10

    print("PHASE 1: Ambulance moving to PATIENT")
    print("─────────────────────────────────────")
    for i in range(steps):
        progress = i / steps
        lat = start_lat + (end_lat - start_lat) * progress
        lng = start_lng + (end_lng - start_lng) * progress
        lat += np.random.uniform(-0.0003, 0.0003)
        lng += np.random.uniform(-0.0003, 0.0003)
        eta = round((steps - i) * 3 / 60, 1)

        await sio.emit('update_location', {
            'emergency_id': emergency_id,
            'lat': round(lat, 6),
            'lng': round(lng, 6),
            'phase': 'to_patient',
            'step': i + 1,
            'total_steps': steps,
            'eta_minutes': eta,
            'status': 'en_route_to_patient'
        })

        print(f"  Step {i+1}/10 → lat:{round(lat,4)} "
              f"lng:{round(lng,4)} ETA:{eta}min")
        await asyncio.sleep(3)

    print()
    print("PATIENT PICKED UP")
    await sio.emit('update_location', {
        'emergency_id': emergency_id,
        'lat': 11.0168,
        'lng': 76.9558,
        'phase': 'patient_picked_up',
        'status': 'patient_onboard',
        'eta_minutes': 0
    })
    await asyncio.sleep(2)

    start_lat, start_lng = 11.0168, 76.9558
    end_lat,   end_lng   = 11.0024, 76.9698

    print()
    print("PHASE 2: Ambulance moving to KMCH HOSPITAL")
    print("────────────────────────────────────────────")
    for i in range(steps):
        progress = i / steps
        lat = start_lat + (end_lat - start_lat) * progress
        lng = start_lng + (end_lng - start_lng) * progress
        lat += np.random.uniform(-0.0003, 0.0003)
        lng += np.random.uniform(-0.0003, 0.0003)
        eta = round((steps - i) * 3 / 60, 1)

        await sio.emit('update_location', {
            'emergency_id': emergency_id,
            'lat': round(lat, 6),
            'lng': round(lng, 6),
            'phase': 'to_hospital',
            'step': i + 1,
            'total_steps': steps,
            'eta_minutes': eta,
            'status': 'en_route_to_hospital'
        })

        print(f"  Step {i+1}/10 → lat:{round(lat,4)} "
              f"lng:{round(lng,4)} ETA:{eta}min")
        await asyncio.sleep(3)

    print()
    print("AMBULANCE ARRIVED AT KMCH HOSPITAL")
    await sio.emit('update_location', {
        'emergency_id': emergency_id,
        'lat': 11.0024,
        'lng': 76.9698,
        'phase': 'arrived',
        'status': 'arrived_at_hospital',
        'eta_minutes': 0
    })

    print()
    print("Simulation complete.")
    print(f"Total time: ~{steps * 3 * 2} seconds")
    print("Patient delivered to KMCH Hospital.")
    await asyncio.sleep(1)
    await sio.disconnect()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USAGE:")
        print("  python simulate_ambulance.py EMG-XXXXXXXX")
        print()
        print("HOW TO GET emergency_id:")
        print("  1. Go to localhost:8000/docs")
        print("  2. POST /emergency/trigger")
        print("  3. Copy emergency_id from response")
        print("  4. Paste it above")
    else:
        asyncio.run(simulate(sys.argv[1]))
