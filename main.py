import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import uuid4
import copy

from ml_vitals import load_model, predict_vitals_anomaly
from routing_agent import find_best_hospital, HOSPITALS, score_hospital, haversine
import socketio
from socket_server import sio, emit_location, emit_confirmed

# Fix encoding issue for logging on Windows
import sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ml_model = None
ml_scaler = None

app = FastAPI(title="AURA Emergency System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HOSPITALS_DB = copy.deepcopy(HOSPITALS)
EMERGENCIES_DB = {}

AMBULANCES_DB = [
  {
    "id": "AMB-001",
    "driver_name": "Kumar Raja",
    "phone": "+919876543210",
    "vehicle_number": "TN33 AB 1234",
    "vehicle_type": "Advanced Life Support",
    "current_lat": 11.0200,
    "current_lng": 76.9600,
    "status": "available",
    "assigned_emergency": None
  },
  {
    "id": "AMB-002", 
    "driver_name": "Ravi Shankar",
    "phone": "+919876543211",
    "vehicle_number": "TN33 CD 5678",
    "vehicle_type": "Basic Life Support",
    "current_lat": 11.0100,
    "current_lng": 76.9500,
    "status": "available",
    "assigned_emergency": None
  },
  {
    "id": "AMB-003",
    "driver_name": "Senthil Kumar",
    "phone": "+919876543212",
    "vehicle_number": "TN33 EF 9012",
    "vehicle_type": "Patient Transport",
    "current_lat": 11.0300,
    "current_lng": 76.9700,
    "status": "available",
    "assigned_emergency": None
  }
]

@app.on_event("startup")
def startup_event():
    global ml_model, ml_scaler
    logger.info("Initializing ML Model...")
    ml_model, ml_scaler = load_model()
    logger.info("AURA System Started Successfully")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Error: {str(exc)}")
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"error": "Internal Server Error", "details": str(exc)})

class EmergencyRequest(BaseModel):
    patient_name: str = "Unknown Patient"
    family_phone: str = "+910000000000"
    patient_lat: float = 11.0168
    patient_lng: float = 76.9558

class HospitalUpdate(BaseModel):
    icu_beds: Optional[int] = None
    has_oxygen: Optional[bool] = None
    has_er_doctor: Optional[bool] = None
    doctor_count: Optional[int] = None
    doctor_available: Optional[bool] = None
    specialty: Optional[str] = None

class VitalsSubmission(BaseModel):
    emergency_id: str
    heart_rate: int
    systolic_bp: int
    diastolic_bp: int
    notes: str = ""

class HospitalAcceptance(BaseModel):
    confirmed_by: str = "ER Admin"
    message: str = ""

class AmbulanceRegister(BaseModel):
    driver_name: str
    phone: str
    vehicle_number: str
    vehicle_type: str = "Basic Life Support"
    current_lat: float = 11.0168
    current_lng: float = 76.9558

class AmbulanceUpdate(BaseModel):
    status: Optional[str] = None
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    assigned_emergency: Optional[str] = None

@app.get("/")
def root():
    return {
        "status": "AURA Online",
        "version": "1.0",
        "ml_model": "IsolationForest loaded" if ml_model else "Not loaded",
        "hospitals_loaded": len(HOSPITALS_DB)
    }

@app.post("/emergency/trigger")
def trigger_emergency(req: EmergencyRequest):
    logger.info("Triggering emergency")
    
    routing_result = find_best_hospital(HOSPITALS_DB, req.patient_lat, req.patient_lng)
    best_hosp = routing_result['best_hospital']
    
    emergency_id = "EMG-" + str(uuid4())[:8].upper()
    
    EMERGENCIES_DB[emergency_id] = {
        "emergency_id": emergency_id,
        "status": "dispatched",
        "request": req.dict() if hasattr(req, 'dict') else req.model_dump(),
        "routing": routing_result,
        "vitals": None,
        "ml_assessment": None,
        "confirmed": False
    }
    
    hospital_id_str = ""
    if best_hosp:
        for idx, h in enumerate(HOSPITALS_DB):
            if h['name'] == best_hosp['name']:
                hospital_id_str = str(idx)
                break
                
    score_breakdown = {
        "score": float(best_hosp['score']) if best_hosp else 0.0,
        "dist_km": float(best_hosp['dist_km']) if best_hosp else 0.0,
        "icu_score": float(best_hosp['icu_score']) if best_hosp else 0.0,
        "readiness_score": float(best_hosp['readiness_score']) if best_hosp else 0.0
    }
    
    nearest_amb = None
    nearest_dist = float('inf')
    for amb in AMBULANCES_DB:
        if amb['status'] == 'available':
            d = haversine(req.patient_lat, req.patient_lng,
                          amb['current_lat'], amb['current_lng'])
            if d < nearest_dist:
                nearest_dist = d
                nearest_amb = amb
                
    if nearest_amb:
        nearest_amb['status'] = 'en_route_to_patient'
        nearest_amb['assigned_emergency'] = emergency_id
        assigned_ambulance = {
            "ambulance_id": nearest_amb['id'],
            "driver_name": nearest_amb['driver_name'],
            "driver_phone": nearest_amb['phone'],
            "vehicle_number": nearest_amb['vehicle_number'],
            "ambulance_eta_minutes": round(nearest_dist / 0.5, 1)
        }
    else:
        assigned_ambulance = None
    
    return {
        "emergency_id": emergency_id,
        "status": "dispatched",
        "hospital_name": best_hosp['name'] if best_hosp else "None",
        "hospital_address": best_hosp.get('address', 'Unknown') if best_hosp else "Unknown",
        "hospital_id": hospital_id_str,
        "eta_minutes": 8,
        "score_breakdown": score_breakdown,
        "routing_formula": "Score=(0.5×Proximity)+(0.3×ICU)+(0.2×Readiness)",
        "all_hospitals_ranked": routing_result.get('all_ranked', []),
        "skipped_hospitals": routing_result.get('skipped_hospitals', []),
        "tracking_url": f"http://localhost:5173/track/{emergency_id}",
        "assigned_ambulance": assigned_ambulance
    }


@app.get("/hospitals")
def get_hospitals(lat: Optional[float] = None, lng: Optional[float] = None):
    hospitals_list = []
    
    if lat is not None and lng is not None:
        ranked = []
        for i, h in enumerate(HOSPITALS_DB):
            h_score = score_hospital(h, lat, lng)
            h_copy = copy.deepcopy(h)
            h_copy.update({
                "id": str(i),
                "address": "Coimbatore",
                "icu_beds": h['icu'],
                "has_oxygen": h['oxygen'],
                "has_er_doctor": h['doctor'],
                "score": h_score['score'],
                "status": "Active"
            })
            ranked.append(h_copy)
            
        ranked.sort(key=lambda x: x['score'], reverse=True)
        for rank, h in enumerate(ranked):
            h['rank'] = rank + 1
            hospitals_list.append(h)
    else:
        for i, h in enumerate(HOSPITALS_DB):
            h_copy = copy.deepcopy(h)
            h_copy.update({
                "id": str(i),
                "address": "Coimbatore",
                "icu_beds": h['icu'],
                "has_oxygen": h['oxygen'],
                "has_er_doctor": h['doctor'],
                "status": "Active"
            })
            hospitals_list.append(h_copy)
            
    return {
        "hospitals": hospitals_list,
        "total": len(HOSPITALS_DB)
    }

@app.patch("/hospitals/{hospital_id}")
def update_hospital(hospital_id: int, update: HospitalUpdate):
    if hospital_id < 0 or hospital_id >= len(HOSPITALS_DB):
        raise HTTPException(status_code=404, detail="Hospital not found")
        
    h = HOSPITALS_DB[hospital_id]
    if update.icu_beds is not None:
        h['icu'] = update.icu_beds
    if update.has_oxygen is not None:
        h['oxygen'] = update.has_oxygen
    if update.has_er_doctor is not None:
        h['doctor'] = update.has_er_doctor
    if update.doctor_count is not None:
        h['doctor_count'] = update.doctor_count
    if update.doctor_available is not None:
        h['doctor_available'] = update.doctor_available
    if update.specialty is not None:
        h['specialty'] = update.specialty
        
    res = find_best_hospital(HOSPITALS_DB, 11.0168, 76.9558)
    
    return {
        "success": True,
        "updated_hospital": h,
        "new_rankings": res['all_ranked'],
        "skipped_count": len(res['skipped_hospitals']),
        "message": f"Rankings updated. {len(res['skipped_hospitals'])} hospitals skipped."
    }

@app.post("/vitals")
def submit_vitals(vitals: VitalsSubmission):
    if vitals.emergency_id not in EMERGENCIES_DB:
        raise HTTPException(status_code=404, detail="Emergency not found")
        
    assessment = predict_vitals_anomaly(vitals.heart_rate, vitals.systolic_bp, vitals.diastolic_bp, ml_model, ml_scaler)
    
    em = EMERGENCIES_DB[vitals.emergency_id]
    em['vitals'] = vitals.model_dump() if hasattr(vitals, 'model_dump') else vitals.dict()
    em['ml_assessment'] = assessment
    
    if assessment['risk_level'] == "CRITICAL":
        hospital_briefing = "PREPARE CRASH CART. ML flagged dangerous vitals."
    elif assessment['risk_level'] == "WARNING":
        hospital_briefing = "Monitor closely. ML detected irregular vitals."
    else:
        hospital_briefing = "Patient stable. Standard admission."
        
    return {
        "success": True,
        "emergency_id": vitals.emergency_id,
        "ml_assessment": assessment,
        "hospital_briefing": hospital_briefing,
        "vitals_received": em['vitals']
    }

@app.post("/emergency/{emergency_id}/accept")
def accept_emergency(emergency_id: str, accept: HospitalAcceptance):
    if emergency_id not in EMERGENCIES_DB:
        raise HTTPException(status_code=404, detail="Emergency not found")
        
    em = EMERGENCIES_DB[emergency_id]
    em['status'] = "confirmed"
    em['confirmed'] = True
    
    return {
        "success": True,
        "emergency_id": emergency_id,
        "status": "confirmed",
        "message": "Bed confirmed. ER team is ready.",
        "eta_minutes": 6,
        "confirmed_by": accept.confirmed_by
    }

@app.get("/emergency/{emergency_id}")
def get_emergency(emergency_id: str):
    if emergency_id not in EMERGENCIES_DB:
        raise HTTPException(status_code=404, detail="Emergency not found")
        
    return EMERGENCIES_DB[emergency_id]

@app.post("/ambulance/register")
def register_ambulance(amb: AmbulanceRegister):
    ambulance_id = "AMB-" + str(uuid4())[:6].upper()
    new_amb = amb.dict() if hasattr(amb, 'dict') else amb.model_dump()
    new_amb["id"] = ambulance_id
    new_amb["status"] = "available"
    new_amb["assigned_emergency"] = None
    
    AMBULANCES_DB.append(new_amb)
    return {
        "success": True,
        "ambulance_id": ambulance_id,
        "driver_name": new_amb["driver_name"],
        "vehicle_number": new_amb["vehicle_number"],
        "message": "Ambulance registered"
    }

@app.get("/ambulance/nearest")
def nearest_ambulance(lat: float, lng: float):
    available = [a for a in AMBULANCES_DB if a["status"] == "available"]
    
    if not available:
        return {
            "nearest_ambulance": None,
            "all_available": [],
            "total_available": 0,
            "message": "No available ambulances found"
        }
    
    for amb in available:
        dist = haversine(lat, lng, amb["current_lat"], amb["current_lng"])
        amb["distance_km"] = round(dist, 2)
        amb["eta_minutes"] = round(dist / 0.5, 1)
        
    available.sort(key=lambda x: x["distance_km"])
    
    return {
        "nearest_ambulance": available[0],
        "all_available": available,
        "total_available": len(available)
    }

@app.get("/ambulance")
def get_ambulance():
    available_count = sum(1 for a in AMBULANCES_DB if a["status"] == "available")
    return {
        "ambulances": AMBULANCES_DB,
        "total": len(AMBULANCES_DB),
        "available": available_count
    }

@app.patch("/ambulance/{ambulance_id}")
def update_ambulance_status(ambulance_id: str, update: AmbulanceUpdate):
    for amb in AMBULANCES_DB:
        if amb["id"] == ambulance_id:
            if update.status is not None:
                amb["status"] = update.status
            if update.current_lat is not None:
                amb["current_lat"] = update.current_lat
            if update.current_lng is not None:
                amb["current_lng"] = update.current_lng
            if update.assigned_emergency is not None:
                amb["assigned_emergency"] = update.assigned_emergency
                
            return {
                "success": True,
                "updated_ambulance": amb
            }
            
    raise HTTPException(status_code=404, detail="Ambulance not found")

app = socketio.ASGIApp(sio, app)
