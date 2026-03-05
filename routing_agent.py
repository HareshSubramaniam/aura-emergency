import math

HOSPITALS = [
    {
        "name": "KMCH Hospital", "lat": 11.0024, "lng": 76.9698, "icu": 8, "oxygen": True, "doctor": True,
        "doctor_count": 3, "doctor_available": True, "specialty": "General Emergency"
    },
    {
        "name": "PSG Hospitals", "lat": 11.0248, "lng": 76.9366, "icu": 6, "oxygen": True, "doctor": True,
        "doctor_count": 3, "doctor_available": True, "specialty": "General Emergency"
    },
    {
        "name": "Sri Ramakrishna", "lat": 11.0090, "lng": 76.9629, "icu": 4, "oxygen": True, "doctor": False,
        "doctor_count": 3, "doctor_available": True, "specialty": "General Emergency"
    },
    {
        "name": "Ganga Hospital", "lat": 11.0198, "lng": 76.9452, "icu": 5, "oxygen": False, "doctor": True,
        "doctor_count": 3, "doctor_available": True, "specialty": "General Emergency"
    },
    {
        "name": "GKN Hospital", "lat": 10.9912, "lng": 76.9612, "icu": 0, "oxygen": True, "doctor": True,
        "doctor_count": 3, "doctor_available": True, "specialty": "General Emergency"
    },
    {
        "name": "City Hospital CBE", "lat": 11.0168, "lng": 76.9558, "icu": 3, "oxygen": True, "doctor": True,
        "doctor_count": 3, "doctor_available": True, "specialty": "General Emergency"
    }
]

def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def score_hospital(hospital, pLat, pLng):
    distance = haversine(pLat, pLng, hospital['lat'], hospital['lng'])
    proximity = 1 / (distance + 1)
    icu_score = min(hospital['icu'] / 10, 1.0)
    has_er_doctor = hospital.get('doctor', False)
    
    if not hospital.get('doctor_available', True):
        has_er_doctor = False
        
    has_oxygen = hospital.get('oxygen', False)
    readiness = (0.5 if has_er_doctor else 0) + (0.5 if has_oxygen else 0)
    score = (0.5 * proximity) + (0.3 * icu_score) + (0.2 * readiness)
    
    return {
        "score": score,
        "dist_km": distance,
        "icu_score": icu_score,
        "readiness_score": readiness
    }

def find_best_hospital(hospitals, pLat, pLng):
    all_ranked = []
    skipped_hospitals = []
    
    for h in hospitals:
        res = score_hospital(h, pLat, pLng)
        h_data = {**h, **res}
        if h.get('icu', 0) == 0:
            h_data['reason'] = "0 ICU beds"
            skipped_hospitals.append(h_data)
        elif not h.get('doctor_available', True):
            h_data['reason'] = "No doctors available"
            skipped_hospitals.append(h_data)
        else:
            all_ranked.append(h_data)
            
    all_ranked.sort(key=lambda x: x['score'], reverse=True)
    
    best_hospital = all_ranked[0] if all_ranked else None
    
    return {
        "best_hospital": best_hospital,
        "score_breakdown": {
            "proximity": 1 / (best_hospital['dist_km'] + 0.1) if best_hospital else 0,
            "icu_score": best_hospital['icu_score'] if best_hospital else 0,
            "readiness": best_hospital['readiness_score'] if best_hospital else 0,
            "total": best_hospital['score'] if best_hospital else 0
        },
        "all_ranked": all_ranked,
        "skipped_hospitals": skipped_hospitals,
        "eta_minutes": 8
    }

if __name__ == "__main__":
    pLat = 11.0168
    pLng = 76.9558
    result = find_best_hospital(HOSPITALS, pLat, pLng)
    print("Best Hospital Details:")
    if result['best_hospital']:
        print("Name:", result['best_hospital']['name'])
        print("Score:", result['best_hospital']['score'])
    print("All ranked:")
    for h in result['all_ranked']:
        print(f" - {h['name']}: {h['score']}")
    print("Skipped check:", [h['name'] for h in result['skipped_hospitals']])
