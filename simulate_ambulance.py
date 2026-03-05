import sys
import asyncio
import socketio
import numpy as np

SERVER_URL = "http://localhost:8000"
sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("Connected to server.")

@sio.event
async def disconnect():
    print("Disconnected from server.")

async def simulate(emergency_id):
    try:
        await sio.connect(SERVER_URL)
    except Exception as e:
        print(f"Error: Could not connect to the backend server at {SERVER_URL}.")
        print(f"Make sure your FastAPI server is running! Details: {e}")
        return
        
    print(f"Simulating ambulance for {emergency_id}")
    await sio.emit('join_emergency', {
        'emergency_id': emergency_id, 
        'role': 'ambulance_simulator'
    })
    
    start_lat = 11.0168
    start_lng = 76.9558
    end_lat   = 11.0024 # KMCH Hospital
    end_lng   = 76.9698
    steps     = 20
    
    for i in range(steps):
        progress = i / (steps - 1) if steps > 1 else 1
        lat = start_lat + (end_lat - start_lat) * progress
        lng = start_lng + (end_lng - start_lng) * progress
        
        if i < steps - 1:
            lat += np.random.uniform(-0.0005, 0.0005)
            lng += np.random.uniform(-0.0005, 0.0005)
        
        try:
            await sio.emit('update_location', {
                'emergency_id': emergency_id,
                'lat': round(lat, 6),
                'lng': round(lng, 6),
                'step': i+1,
                'total_steps': steps
            })
            
            print(f"Step {i+1}/20: lat={round(lat,4)} lng={round(lng,4)}")
        except Exception as e:
            print(f"Failed to emit location update: {e}")
            break
            
        await asyncio.sleep(3)
    
    print("Ambulance reached hospital.")
    await sio.disconnect()

if __name__ == "__main__":
    emergency_id = sys.argv[1] if len(sys.argv) > 1 else "EMG-TEST001"
    try:
        asyncio.run(simulate(emergency_id))
    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
