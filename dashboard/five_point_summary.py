import numpy as np
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

@app.get("/price-summary")
async def get_price_summary():
    # Fetch data from Firebase Firestore where 'sold' is True
    docs = db.collection("candidates").where("sold", "==", True).stream()
    
    prices = [doc.to_dict().get("price", 0) for doc in docs if "price" in doc.to_dict()]

    if not prices:
        return {"message": "No data found for sold candidates"}

    # Compute five-point summary
    min_price = np.min(prices)
    max_price = np.max(prices)
    mean_price = np.mean(prices)
    q25 = np.percentile(prices, 25)
    q75 = np.percentile(prices, 75)

    # Convert NumPy types to native Python types
    return {
        "min": float(min_price),
        "max": float(max_price),
        "mean": float(mean_price),
        "25th_percentile": float(q25),
        "75th_percentile": float(q75)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)