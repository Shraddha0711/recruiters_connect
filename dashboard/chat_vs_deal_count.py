from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import os
load_dotenv()

# Initialize Firebase
cred = credentials.Certificate(os.getenv("CRED_PATH"))  # Update the path
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

@app.get("/chat-deal-counts")
def get_chat_deal_counts():
    try:
        # Reference to 'messages' collection
        messages_ref = db.collection("messages")
        messages = messages_ref.get()

        # Initialize counters
        total_chat_initialize = 0
        total_deal_final = 0

        # Iterate through each document in the messages collection
        for message in messages:
            data = message.to_dict()
            content = data.get("content", {})

            if isinstance(content, dict):  # Ensure content is a dictionary
                content_type = content.get("type", "")

                if content_type == "candidate_card":
                    total_chat_initialize += 1
                elif content_type == "quote_price":
                    total_deal_final += 1

        return {
            "total_chat_initialize": total_chat_initialize,
            "total_deal_final": total_deal_final
        }

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)