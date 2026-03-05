import socketio
import uvicorn
from fastapi import FastAPI
import time

# Create AsyncServer
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*'
)

@sio.event
async def connect(sid, environ):
    print(f"INFO: Client connected: {sid}")

@sio.event
async def join_emergency(sid, data):
    emergency_id = data.get('emergency_id')
    role = data.get('role', 'unknown')
    if emergency_id:
        sio.enter_room(sid, emergency_id)
        print(f"INFO: {role} joined room {emergency_id}")

@sio.event
async def disconnect(sid):
    print(f"INFO: Client disconnected: {sid}")

@sio.event
async def update_location(sid, data):
    emergency_id = data.get('emergency_id')
    lat = data.get('lat')
    lng = data.get('lng')
    if emergency_id:
        await sio.emit('ambulance_position', {
            'lat': lat,
            'lng': lng,
            'emergency_id': emergency_id,
            'timestamp': time.time()
        }, room=emergency_id)

async def emit_location(emergency_id, lat, lng):
    await sio.emit('ambulance_position', {
        'lat': lat,
        'lng': lng,
        'emergency_id': emergency_id
    }, room=emergency_id)

async def emit_confirmed(emergency_id, hospital_name):
    await sio.emit('hospital_confirmed', {
        'emergency_id': emergency_id,
        'hospital_name': hospital_name,
        'message': "Bed confirmed. ER team is ready.",
        'status': "confirmed"
    }, room=emergency_id)
