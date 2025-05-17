from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from dotenv import load_dotenv
import os
load_dotenv()

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
# Initialize Firebase
cred = credentials.Certificate(os.getenv("CRED_PATH"))  # Replace with your actual JSON file path
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.get("/bids/metrics")
async def get_bid_metrics():
    try:
        # Fetch all documents from 'biding' collection
        bids_ref = db.collection("biding")
        bids = bids_ref.stream()

        total_bids = 0
        fulfilled_bids = 0
        fulfill_times = []

        for bid in bids:
            data = bid.to_dict()
            total_bids += 1

            # Check if the bid is fulfilled
            if data.get("fulfil") == True:
                fulfilled_bids += 1

                # Ensure created_at and fulfil_time exist and are timestamps
                created_at = data.get("created_at")
                fulfil_time = data.get("fulfil_time")

                if isinstance(created_at, datetime) and isinstance(fulfil_time, datetime):
                    fulfill_times.append((fulfil_time - created_at).total_seconds())

        # Calculate average fulfill time (convert seconds to days)
        avg_fulfill_time_seconds = sum(fulfill_times) / len(fulfill_times) if fulfill_times else 0
        avg_fulfill_time_days = avg_fulfill_time_seconds / 86400  # Convert to days

        return {
            "total_bids": total_bids,
            "fulfilled_bids": fulfilled_bids,
            "avg_fulfill_time_days": round(avg_fulfill_time_days, 2)  # Rounded to 2 decimal places
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)