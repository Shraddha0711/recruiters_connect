from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from firebase_admin import credentials, firestore, initialize_app
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Firebase
cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))
initialize_app(cred)
db = firestore.client()

app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model
class Biding(BaseModel):
    city: str
    country: str
    created_at: datetime
    ctc: float
    experience: float
    expired: bool = False
    expired_in: int
    fulfil: bool = False
    recruiter_id: str
    role: str
    skills: List[str]

# Create Biding
# @app.post("/biding/", response_model=dict)
# def create_biding(biding: Biding):
#     doc_ref = db.collection("biding").add(biding.dict())
#     return {"id": doc_ref[1].id, "message": "Biding created successfully"}

@app.post("/biding/", response_model=dict)
def create_biding(biding: Biding):
    # Generate unique ID using timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S%f")  # e.g., 20250512-104530123456
    custom_id = f"bid-{timestamp}"

    db.collection("biding").document(custom_id).set(biding.dict())
    return {"id": custom_id, "message": "Biding created successfully"}

# Delete Biding
@app.delete("/biding/{biding_id}", response_model=dict)
def delete_biding(biding_id: str):
    doc_ref = db.collection("biding").document(biding_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Biding not found")
    doc_ref.delete()
    return {"message": "Biding deleted successfully"}

# List all Biding where fulfil == false and expired == false
# @app.get("/biding/", response_model=Dict[str, List[Dict[str, Any]]])
# def list_bidings():
#     try:
#         biding_docs = db.collection("biding")\
#             .where("fulfil", "==", False)\
#             .where("expired", "==", False)\
#             .stream()

#         bidings = [{"id": doc.id, **doc.to_dict()} for doc in biding_docs]
#         return {"bidings": bidings}
#     except Exception as e:
#         return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/biding/", response_model=Dict[str, List[Dict[str, Any]]])
def list_bidings():
    try:
        now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)

        # Step 1: Check and update expiration status
        docs_to_check = db.collection("biding").where("expired", "==", False).stream()
        for doc in docs_to_check:
            data = doc.to_dict()
            created_at = data.get("created_at")
            expired_in = data.get("expired_in")

            if created_at and expired_in is not None:
                # Ensure created_at is timezone-aware
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                expiry_time = created_at + timedelta(days=expired_in)

                if expiry_time < now_utc:
                    db.collection("biding").document(doc.id).update({
                        "expired": True,
                        "fulfil": False
                    })

        # Step 2: Return filtered bidings
        biding_docs = db.collection("biding")\
            .where("fulfil", "==", False)\
            .where("expired", "==", False)\
            .stream()

        bidings = [{"id": doc.id, **doc.to_dict()} for doc in biding_docs]
        return {"bidings": bidings}

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
