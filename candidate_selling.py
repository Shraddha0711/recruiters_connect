from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from firebase_admin import credentials, firestore, initialize_app
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Firebase Setup
cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))
initialize_app(cred)
db = firestore.client()

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SellRequest(BaseModel):
    buyer_id: str
    seller_id: str
    candidate_id: str
    connects: int

@app.post("/sell-candidate/")
async def sell_candidate(data: SellRequest):
    try:
        timestamp = datetime.utcnow()

        # 1. Add to candidate_selling collection
        db.collection("candidate_selling").add({
            "buyer_id": data.buyer_id,
            "seller_id": data.seller_id,
            "candidate_id": data.candidate_id,
            "connects": data.connects,
            "timestamp": timestamp
        })

        # 2. Update recruiters - decrement buyer connects
        buyer_ref = db.collection("recruiters").document(data.buyer_id)
        seller_ref = db.collection("recruiters").document(data.seller_id)

        buyer_doc = buyer_ref.get()
        seller_doc = seller_ref.get()

        if not buyer_doc.exists or not seller_doc.exists:
            raise HTTPException(status_code=404, detail="Buyer or Seller not found")

        buyer_connects = buyer_doc.to_dict().get("connects", 0)
        seller_connects = seller_doc.to_dict().get("connects", 0)

        if buyer_connects < data.connects:
            raise HTTPException(status_code=400, detail="Buyer doesn't have enough connects")

        buyer_ref.update({"connects": buyer_connects - data.connects})
        seller_ref.update({"connects": seller_connects + data.connects})

        # Update num_of_deals for both
        buyer_num_of_deals = buyer_doc.to_dict().get("num_of_deals", 0)
        seller_num_of_deals = seller_doc.to_dict().get("num_of_deals", 0)

        buyer_ref.update({"num_of_deals": buyer_num_of_deals + 1})
        seller_ref.update({"num_of_deals": seller_num_of_deals + 1})

        # 3. Update candidate info
        candidate_ref = db.collection("candidates").document(data.candidate_id)
        candidate_doc = candidate_ref.get()

        if not candidate_doc.exists:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate_ref.update({
            "purchased_by": data.buyer_id,
            "sold": True,
            "sold_time": timestamp,
            "price": data.connects
        })

        updated_candidate = candidate_ref.get().to_dict()
        updated_candidate["id"] = data.candidate_id  # include ID if needed
        return updated_candidate

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
