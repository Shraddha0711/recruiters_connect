from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv 
import os
load_dotenv()

# Initialize Firebase
cred = credentials.Certificate(os.getenv("CRED_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/submit-feedback/")
def submit_feedback(user_id: str, rating: int = 0, feedback: str | None = None):
    if rating < 0 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")
    
    feedback_data = {
        "user_id": user_id,
        "rating": rating,
        "feedback": feedback,
    }
    db.collection("feedbacks").add(feedback_data)
    return {"message": "Feedback submitted successfully"}

@app.get("/feedbacks/")
def get_feedbacks():
    feedbacks_ref = db.collection("feedbacks").stream()
    feedback_list = [fb.to_dict() for fb in feedbacks_ref]
    return feedback_list

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
