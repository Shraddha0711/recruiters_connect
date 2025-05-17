from fastapi import FastAPI, HTTPException, Header, Body
from pydantic import BaseModel
import requests
import firebase_admin
from firebase_admin import credentials, firestore, auth
from typing import Optional
import os
import uvicorn
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from datetime import timezone
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


cred = credentials.Certificate(os.getenv("CRED_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()

class UserSignUp(BaseModel):
    email: str
    password: str

class UserSignIn(BaseModel):
    email: str
    password: str


@app.post("/signup")
def sign_up(user: UserSignUp):
    # Firebase sign-up endpoint
    sign_up_url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}'
    sign_up_payload = {
        "email": user.email,
        "password": user.password,
        "returnSecureToken": True
    }
    sign_up_response = requests.post(sign_up_url, json=sign_up_payload)
    
    if sign_up_response.status_code == 200:
        id_token = sign_up_response.json().get('idToken')
        
        # Send email verification
        verify_email_url = f'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}'
        verify_email_payload = {
            "requestType": "VERIFY_EMAIL",
            "idToken": id_token
        }
        verify_email_response = requests.post(verify_email_url, json=verify_email_payload)
        
        if verify_email_response.status_code == 200:
            return {"message": "Verification email sent. Please check your inbox.", "token_id" : id_token}
        else:
            raise HTTPException(status_code=verify_email_response.status_code, detail=verify_email_response.json())
    else:
        raise HTTPException(status_code=sign_up_response.status_code, detail=sign_up_response.json())
    


@app.post("/signin")
def sign_in(user: UserSignIn):
    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}'
    payload = {
        "email": user.email,
        "password": user.password,
        "returnSecureToken": True
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        id_token = data.get("idToken")

        try:
            decoded_token = auth.verify_id_token(id_token)
            uid = decoded_token["uid"]
            user_doc = db.collection("recruiters").document(uid).get()

            if user_doc.exists:
                user_data = user_doc.to_dict()
                if user_data.get("suspended"):
                    raise HTTPException(status_code=403, detail="Account is suspended. Please contact support.")
                return data
            else:
                return data
                # raise HTTPException(status_code=404, detail="User profile not found.")

        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())




class UserProfileCreate(BaseModel):
    name: str
    city: str
    country: str
    phone_number: str
    email: str
    bio: Optional[str] = None
    tags: Optional[list[str]] = []
    profile_pic_url: Optional[str] = None

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    tags: Optional[list[str]] = None
    profile_pic_url: Optional[str] = None
    
    class Config:
        # This ensures that omitted fields aren't included with default values
        extra = "ignore"
        
        # Make validation less strict for partial updates
        validate_assignment = True


class PasswordResetRequest(BaseModel):
    email: str

@app.post("/password-reset")
def send_password_reset_email(request: PasswordResetRequest):
    url = f'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}'
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": request.email
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return {"message": "Password reset email sent."}
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    

@app.post("/user/profile")
def create_user_profile(profile: UserProfileCreate, token: str):
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]
        user_ref = db.collection("recruiters").document(uid)

        now = datetime.utcnow()

        user_data = {
            "name": profile.name,
            "city": profile.city,
            "country": profile.country,
            "phone_number": profile.phone_number,
            "email": profile.email,
            "bio": profile.bio,
            "tags": profile.tags or [],
            "role": "Recruiter",
            "rating": 0,
            "no_of_people_rated": 0,
            "verified_badge": False,
            "num_candidates_listed": 0,
            "created_at": now,
            "updated_at": now,
            "num_of_deals": 0,
            "sponsored": {"status": False, "created_at": None, "plan_name": None, "end_date": None},
            "highlighted": False,
            "bookmarked_candidates": [],
            "connects": 100,
            "last_seen": None,
            "online": None,
            "suspended": False,
            "id": uid,
            "profile_pic_url": profile.profile_pic_url or None,
        }

        user_ref.set(user_data)
        return {"message": "User profile created successfully."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@app.patch("/user/profile/update")
def update_user_profile(token: str = Header(...), update: dict = Body(...)):
    """name, city, country, phone_number, email, 
            bio, tags = [], profile_pic_url"""
    try:
        # Verify token
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]

        # Get user document reference
        user_ref = db.collection("recruiters").document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User profile not found")

        # Only update fields that are explicitly included in the request
        # Use the raw dictionary instead of a Pydantic model
        update_data = {k: v for k, v in update.items() if k in [
            "name", "city", "country", "phone_number", "email", 
            "bio", "tags", "profile_pic_url"
        ]}
        
        # Only proceed if there's actual data to update
        if update_data:
            # Add updated timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            # Update only the specified fields in Firestore
            user_ref.update(update_data)
            
            return {"message": "Profile updated successfully."}
        else:
            return {"message": "No valid fields to update."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/logout")
def logout(token: str):
    try:
        # Verify the ID token and get the user UID
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]

        # Revoke all refresh tokens for the user
        auth.revoke_refresh_tokens(uid)

        return {"message": "User logged out successfully."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/verify-token")
def verify_token(token: str = Header(None)):
    try:
        # Decode and verify the Firebase ID token (disable IAM check)
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        uid = decoded_token["uid"]

        return {
            "message": "Token is valid.",
            "user_id": uid,
            "email": decoded_token.get("email"),
            "expires_at": datetime.utcfromtimestamp(decoded_token["exp"]).strftime("%Y-%m-%d %H:%M:%S UTC")
        }

    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired. Please log in again.")
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token has been revoked.")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

from fastapi import Depends

@app.delete("/user/delete")
def delete_user_account(token: str = Header(...)):
    try:
        # Verify Firebase token
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]

        # Delete user from Firebase Authentication
        auth.delete_user(uid)

        # Delete user profile from Firestore
        db.collection("recruiters").document(uid).delete()

        # Query candidates where created_by == uid and sold == False
        candidates_ref = db.collection("candidates")
        query = candidates_ref.where("created_by", "==", uid).where("sold", "==", False).stream()

        # Delete each matching candidate document
        for candidate in query:
            candidate.reference.delete()

        return {"message": "User account and related unsold candidate profiles deleted successfully."}

    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



# Entry point to run the FastAPI app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)