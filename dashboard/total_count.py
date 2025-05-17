from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os   
from dotenv import load_dotenv
load_dotenv()
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
cred = credentials.Certificate(os.getenv("CRED_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()

app = FastAPI()
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/counts")
def get_counts():
    try:
        # Fetch recruiters count
        recruiters_ref = db.collection("recruiters")
        recruiters_count = len(recruiters_ref.get())

        # Fetch candidates count
        candidates_ref = db.collection("candidates")
        candidates_count = len(candidates_ref.get())

        return {"recruiters_count": recruiters_count, "candidates_count": candidates_count}

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
