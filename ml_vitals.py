import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os

def generate_training_data():
    np.random.seed(42)
    hr_normal = np.clip(np.random.normal(75, 12, 170), 55, 110)
    sys_normal = np.clip(np.random.normal(120, 15, 170), 90, 160)
    dia_normal = np.clip(np.random.normal(80, 10, 170), 60, 100)
    
    hr_outliers = [30,35,28,160,170,180,155,165,40,45,32,38,175,185,165,42,36,190,195,158,25,29,200,210,33,37,188,192,22,26]
    sys_outliers = [55,60,50,190,200,195,185,210,58,62,52,57,205,215,192,64,53,220,225,188,45,48,230,235,56,60,218,222,40,44]
    dia_outliers = [30,35,28,120,130,125,118,135,32,36,29,33,128,140,122,38,31,145,150,120,22,25,155,160,34,37,142,148,20,24]
    
    df_normal = pd.DataFrame({'heart_rate': hr_normal, 'systolic_bp': sys_normal, 'diastolic_bp': dia_normal})
    df_outliers = pd.DataFrame({'heart_rate': hr_outliers, 'systolic_bp': sys_outliers, 'diastolic_bp': dia_outliers})
    
    return pd.concat([df_normal, df_outliers], ignore_index=True)

def train_model():
    df = generate_training_data()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df)
    
    model = IsolationForest(n_estimators=100, contamination=0.15, random_state=42)
    model.fit(X_scaled)
    
    joblib.dump(model, 'vitals_model.pkl')
    joblib.dump(scaler, 'vitals_scaler.pkl')
    
    return model, scaler

def load_model():
    if os.path.exists('vitals_model.pkl') and os.path.exists('vitals_scaler.pkl'):
        model = joblib.load('vitals_model.pkl')
        scaler = joblib.load('vitals_scaler.pkl')
        return model, scaler
    else:
        return train_model()

def predict_vitals_anomaly(heart_rate, systolic_bp, diastolic_bp, model=None, scaler=None):
    if model is None or scaler is None:
        if heart_rate < 50 or systolic_bp < 80:
            risk_level = "CRITICAL"
        elif heart_rate > 130 or systolic_bp > 170:
            risk_level = "WARNING"
        else:
            risk_level = "STABLE"
            
        return {
            "is_anomaly": risk_level != "STABLE",
            "risk_level": risk_level,
            "confidence": 1.0,
            "anomaly_score": 0.0,
            "message": f"Rules-based fallback output: {risk_level}",
            "method": "rules"
        }
        
    X_new = pd.DataFrame({'heart_rate': [heart_rate], 'systolic_bp': [systolic_bp], 'diastolic_bp': [diastolic_bp]})
    X_new_scaled = scaler.transform(X_new)
    
    prediction = model.predict(X_new_scaled)[0]
    score = model.decision_function(X_new_scaled)[0]
    
    if prediction == -1 and score < -0.15:
        risk_level = "CRITICAL"
    elif prediction == -1 and score >= -0.15:
        risk_level = "WARNING"
    else:
        risk_level = "STABLE"
        
    return {
        "is_anomaly": bool(prediction == -1),
        "risk_level": risk_level,
        "confidence": float(abs(score)),
        "anomaly_score": float(score),
        "message": f"ML detected {risk_level} condition",
        "method": "IsolationForest"
    }

if __name__ == "__main__":
    m, s = load_model()
    test_cases = [
        (75, 120, 80),
        (30, 55, 30),
        (170, 200, 130),
        (95, 130, 85),
        (22, 40, 20)
    ]
    for hr, sys, dia in test_cases:
        res = predict_vitals_anomaly(hr, sys, dia, m, s)
        print(f"Vitals: ({hr}, {sys}, {dia}) -> {res['risk_level']}")
