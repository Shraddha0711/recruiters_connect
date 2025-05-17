from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from firebase_admin import credentials, firestore, initialize_app
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os 
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

# Firebase setup
cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))  # Path to your service account key
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

# Pydantic model to represent candidate data with updated fields
class Candidate(BaseModel):
    name: str
    city: str
    country: str
    ctc: float
    notice_period: str
    linkedin: Optional[str] = None
    role: str
    skills: List[str]
    experience: float
    contact_number: str
    email: str
    created_by: str
    candidate_id: Optional[str] = None
    created_at: Optional[datetime] = None
    bookmarked_by: Optional[List[str]] = None
    sold: Optional[bool] = False

# Helper function to save candidate to Firestore
def save_candidate(candidate: Candidate):
    candidate_dict = candidate.dict()
    # Initialize empty bookmarked_by array if it doesn't exist
    if candidate_dict.get('bookmarked_by') is None:
        candidate_dict['bookmarked_by'] = []
    
    # Set created_at timestamp
    candidate_dict['created_at'] = firestore.SERVER_TIMESTAMP
    
    # Create a new document in Firestore and get its document ID
    doc_ref = db.collection("candidates").document()
    candidate_dict["candidate_id"] = doc_ref.id  # Assign the document ID as candidate_id
    doc_ref.set(candidate_dict)  # Save the candidate
    return doc_ref.id

# Endpoint to create a new candidate
@app.post("/candidates/")
async def create_candidate(candidate: Candidate):
    try:
        candidate_id = save_candidate(candidate)
        return {"message": "Candidate created successfully", "candidate_id": candidate_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to create multiple candidates in bulk
@app.post("/candidates/bulk/")
async def bulk_create_candidates(candidates: List[Candidate]):
    try:
        batch = db.batch()
        for candidate in candidates:
            doc_ref = db.collection("candidates").document()
            candidate_dict = candidate.dict()
            candidate_dict["candidate_id"] = doc_ref.id  # Assign document ID as candidate_id
            candidate_dict["bookmarked_by"] = []
            candidate_dict["created_at"] = firestore.SERVER_TIMESTAMP
            candidate_dict["sold"] = False
            batch.set(doc_ref, candidate_dict)
        
        batch.commit()  # Commit all the bulk operations at once
        return {"message": f"{len(candidates)} candidates created successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to get all candidates
@app.get("/candidates/")
async def get_all_candidates():
    try:
        candidates_ref = db.collection("candidates").stream()
        candidates = [candidate.to_dict() for candidate in candidates_ref]
        return {"candidates": candidates}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to search candidates by keyword (match in any field)
@app.get("/candidates/search/")
async def search_candidates(keyword: str):
    try:
        candidates_ref = db.collection("candidates").stream()
        matched_candidates = []
        
        for candidate in candidates_ref:
            candidate_data = candidate.to_dict()
            if any(keyword.lower() in str(value).lower() for value in candidate_data.values() if isinstance(value, (str, int, float))):
                matched_candidates.append(candidate_data)

        return matched_candidates
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to filter candidates by multiple fields
@app.get("/candidates/filter/")
async def filter_candidates(
    city: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    ctc: Optional[float] = Query(None),
    role: Optional[str] = Query(None),
    experience: Optional[float] = Query(None),
    notice_period: Optional[str] = Query(None),
    skills: Optional[List[str]] = Query(None),
    sold: Optional[bool] = Query(None),
):
    try:
        candidates_ref = db.collection("candidates").stream()
        filtered_candidates = []

        for candidate in candidates_ref:
            candidate_data = candidate.to_dict()
            if (
                (city is None or candidate_data.get("city", "").lower() == city.lower()) and
                (country is None or candidate_data.get("country", "").lower() == country.lower()) and
                (ctc is None or candidate_data.get("ctc", float("inf")) <= ctc) and
                (role is None or candidate_data.get("role", "").lower() == role.lower()) and
                (experience is None or candidate_data.get("experience", 0) >= experience) and
                (notice_period is None or candidate_data.get("notice_period", "").lower() == notice_period.lower()) and
                (skills is None or ("skills" in candidate_data and all(skill.lower() in [s.lower() for s in candidate_data["skills"]] for skill in skills))) and
                (sold is None or candidate_data.get("sold", False) == sold)
            ):
                filtered_candidates.append(candidate_data)

        return filtered_candidates
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to bookmark a candidate
@app.post("/candidates/{candidate_id}/bookmark/")
async def bookmark_candidate(candidate_id: str, recruiter_id: str):
    try:
        candidate_ref = db.collection("candidates").document(candidate_id)
        recruiter_ref = db.collection("recruiters").document(recruiter_id)
        
        candidate = candidate_ref.get()
        recruiter = recruiter_ref.get()
        
        if not candidate.exists:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        candidate_data = candidate.to_dict()
        if recruiter_id not in candidate_data.get("bookmarked_by", []):
            # Update bookmarked_by list in candidate document
            bookmarked_by = candidate_data.get("bookmarked_by", [])
            bookmarked_by.append(recruiter_id)
            candidate_ref.update({"bookmarked_by": bookmarked_by})
        
        if recruiter.exists:
            recruiter_data = recruiter.to_dict()
            if "bookmarked_candidates" not in recruiter_data:
                recruiter_data["bookmarked_candidates"] = []
            if candidate_id not in recruiter_data["bookmarked_candidates"]:
                recruiter_data["bookmarked_candidates"].append(candidate_id)
                recruiter_ref.update({"bookmarked_candidates": recruiter_data["bookmarked_candidates"]})
        else:
            recruiter_ref.set({"bookmarked_candidates": [candidate_id]})
        
        return {"message": "Candidate bookmarked successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to list all bookmarks for a recruiter
@app.get("/recruiters/{recruiter_id}/bookmarks/")
async def list_bookmarked_candidates(recruiter_id: str):
    try:
        recruiter_ref = db.collection("recruiters").document(recruiter_id)
        recruiter = recruiter_ref.get()
        
        if not recruiter.exists:
            return {"message": "No bookmarks found"}
        
        recruiter_data = recruiter.to_dict()
        candidate_ids = recruiter_data.get("bookmarked_candidates", [])
        
        if not candidate_ids:
            return {"message": "No bookmarks found"}
        
        candidates = []
        for candidate_id in candidate_ids:
            candidate_ref = db.collection("candidates").document(candidate_id)
            candidate_doc = candidate_ref.get()
            if candidate_doc.exists:
                candidates.append(candidate_doc.to_dict())
        
        return candidates
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to remove a bookmark
@app.delete("/candidates/{candidate_id}/bookmark/")
async def remove_bookmark(candidate_id: str, recruiter_id: str):
    try:
        candidate_ref = db.collection("candidates").document(candidate_id)
        recruiter_ref = db.collection("recruiters").document(recruiter_id)
        
        candidate = candidate_ref.get()
        recruiter = recruiter_ref.get()
        
        if not candidate.exists:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        candidate_data = candidate.to_dict()
        if recruiter_id in candidate_data.get("bookmarked_by", []):
            bookmarked_by = candidate_data.get("bookmarked_by", [])
            bookmarked_by.remove(recruiter_id)
            candidate_ref.update({"bookmarked_by": bookmarked_by})
        
        if recruiter.exists:
            recruiter_data = recruiter.to_dict()
            if "bookmarked_candidates" in recruiter_data and candidate_id in recruiter_data["bookmarked_candidates"]:
                recruiter_data["bookmarked_candidates"].remove(candidate_id)
                recruiter_ref.update({"bookmarked_candidates": recruiter_data["bookmarked_candidates"]})
        
        return {"message": "Bookmark removed successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint to delete a candidate
@app.delete("/candidates/{candidate_id}/")
async def delete_candidate(candidate_id: str):
    try:
        candidate_ref = db.collection("candidates").document(candidate_id)
        candidate = candidate_ref.get()

        if candidate.exists:
            candidate_ref.delete()
            return {"message": "Candidate deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Candidate not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


