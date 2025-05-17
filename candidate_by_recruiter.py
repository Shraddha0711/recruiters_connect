from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
load_dotenv()

# Initialize Firebase Admin SDK
cred = credentials.Certificate("path/to/your/firebase_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/get_candidates/{recruiter_id}")
async def get_candidates(recruiter_id: str):
    try:
        candidates_ref = db.collection("candidates") 
        query = candidates_ref.where("created_by", "==", recruiter_id).stream()

        candidates = []
        for doc in query:
            candidates.append(doc.to_dict())

        if not candidates:
            raise HTTPException(status_code=404, detail="No candidates found for this recruiter_id")

        return {"status": "success", "candidates": candidates}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)