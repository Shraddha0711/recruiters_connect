from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
load_dotenv()
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

# Initialize Firebase
cred = credentials.Certificate(os.getenv("CRED_PATH"))  # Update this with your Firebase JSON file
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize FastAPI app
app = FastAPI()
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/average_profile_aging")
async def get_average_profile_aging():
    try:
        # Fetch candidates where sold is false
        candidates_ref = db.collection("candidates").where("sold", "==", False).stream()
        
        aging_days = []
        current_time = datetime.now(timezone.utc)  # Get current UTC time

        for candidate in candidates_ref:
            data = candidate.to_dict()
            created_at = data.get("created_at")

            if created_at:
                # Convert Firestore timestamp to datetime
                created_at_dt = created_at if isinstance(created_at, datetime) else created_at.to_datetime()
                aging_days.append((current_time - created_at_dt).days)

        # Compute the average aging time
        avg_aging_time = sum(aging_days) / len(aging_days) if aging_days else 0
        
        return {"average_profile_aging_days": avg_aging_time}

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)