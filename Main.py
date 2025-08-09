#!/usr/bin/env python3
"""
API de résumage avec quota utilisateur depuis MySQL
Fonctionnalités :
- Authentification par clé API stockée en base MySQL
- Mode 'free' = 20 requêtes/jour, mode 'pro' = illimité
- Limite de fréquence : 1 requête / seconde par utilisateur
- Résumage avec Hugging Face Transformers
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from transformers import pipeline
from datetime import datetime, date
import pymysql
import time

# ================= CONFIGURATION =================
DB_CONFIG = {
    "host": "TON_SERVEUR_MYSQL",
    "user": "TON_UTILISATEUR",
    "password": "TON_MOT_DE_PASSE",
    "database": "TA_BASE",
    "cursorclass": pymysql.cursors.DictCursor
}

DEFAULT_MODEL = "sshleifer/distilbart-cnn-12-6"
DAILY_LIMIT = 20  # quota gratuit

# ================= FASTAPI APP =================
app = FastAPI(title="API Résumage avec Quota MySQL")

# Cache du modèle pour éviter les rechargements
SUMMARIZER = pipeline("summarization", model=DEFAULT_MODEL)

# ================= MODELS =================
class TexteReq(BaseModel):
    content: str
    max_length: int = 130
    min_length: int = 30

# ================= FONCTIONS UTILES =================
def get_db_connection():
    """Connexion à MySQL"""
    return pymysql.connect(**DB_CONFIG)

def get_user_from_db(api_key: str):
    """Récupère les infos utilisateur depuis MySQL"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE api_key=%s", (api_key,))
        user = cur.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    return user

def update_user_usage(user_id: int):
    """Met à jour le compteur d'utilisation"""
    conn = get_db_connection()
    today = date.today()
    with conn.cursor() as cur:
        cur.execute("SELECT last_request_date, requests_today, last_request_time FROM users WHERE id=%s", (user_id,))
        u = cur.fetchone()

        # Limite de 1 requête / seconde
        now_ts = time.time()
        if u["last_request_time"] and now_ts - float(u["last_request_time"]) < 1:
            conn.close()
            raise HTTPException(status_code=429, detail="Trop de requêtes, attendez 1 seconde.")

        # Reset si nouveau jour
        if u["last_request_date"] != today:
            cur.execute(
                "UPDATE users SET requests_today=1, last_request_date=%s, last_request_time=%s WHERE id=%s",
                (today, now_ts, user_id)
            )
        else:
            cur.execute(
                "UPDATE users SET requests_today=requests_today+1, last_request_time=%s WHERE id=%s",
                (now_ts, user_id)
            )
    conn.commit()
    conn.close()

# ================= AUTHENTIFICATION + QUOTA =================
def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Clé API manquante")

    user = get_user_from_db(x_api_key)

    # Vérif quota si mode free
    if user["plan"] == "free":
        today = date.today()
        if user["last_request_date"] != today:
            user["requests_today"] = 0  # reset
        if user["requests_today"] >= DAILY_LIMIT:
            raise HTTPException(status_code=429, detail="Quota journalier atteint. Passez au plan PRO.")

    update_user_usage(user["id"])
    return user

# ================= ENDPOINTS =================
@app.post("/resume")
def resumage(req: TexteReq, user=Depends(verify_api_key)):
    summary = SUMMARIZER(req.content, max_length=req.max_length, min_length=req.min_length, do_sample=False)
    return {
        "user_id": user["id"],
        "plan": user["plan"],
        "summary": summary[0]["summary_text"]
    }

# ================= MAIN =================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_resume_mysql:app", host="0.0.0.0", port=8000, reload=True)
