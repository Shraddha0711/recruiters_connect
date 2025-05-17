import os
from datetime import datetime

import stripe
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client

# Load environment variables
load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Stripe
domain = os.getenv("DOMAIN")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store Stripe customer ID in app state (for demo purposes)
app.state.stripe_customer_id = None

# ---------------------------- MODELS ----------------------------

class ProductInfo(BaseModel):
    product_name: str
    product_price: float
    currency: str = "usd"
    product_image: str = "https://i.imgur.com/EHyR2nP.png"
    product_description: str = ""
    user_id: str = ""
    number_of_connects: int = 0

# ---------------------------- ROUTES ----------------------------

@app.get("/success")
async def success():
    return {"status": "success"}

@app.get("/cancel")
async def cancel():
    return {"status": "cancel"}

@app.post("/create-checkout-session")
async def create_checkout_session(product_info: ProductInfo):
    # Create customer once (demo purpose only)
    if not app.state.stripe_customer_id:
        customer = stripe.Customer.create(description="Demo customer")
        app.state.stripe_customer_id = customer["id"]

    unit_amount = int(product_info.product_price * 100)

    checkout_session = stripe.checkout.Session.create(
        customer=app.state.stripe_customer_id,
        success_url=domain+"/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=domain+"/cancel",
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": product_info.currency,
                "product_data": {
                    "name": product_info.product_name,
                    "images": [product_info.product_image],
                    "description": product_info.product_description,
                },
                "unit_amount": unit_amount,
            },
            "quantity": 1,
        }],
        metadata={
            "user_id": product_info.user_id,
            "number_of_connects": product_info.number_of_connects,
        },
    )

    return {"sessionId": checkout_session["id"], "url": checkout_session.url}

@app.post("/create-portal-session")
async def create_portal_session():
    session = stripe.billing_portal.Session.create(
        customer=app.state.stripe_customer_id,
        return_url=domain
    )
    return {"url": session.url}

@app.post("/webhook")
async def webhook_received(request: Request, stripe_signature: str = Header(None)):
    data = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=data,
            sig_header=stripe_signature,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        return {"error": str(e)}

    event_type = event['type']
    session = event['data']['object']

    if event_type == 'checkout.session.completed':
        return {"status": "checkout session completed"}
    elif event_type == 'payment_intent.succeeded':
        handle_checkout_session(session)
        return {"status": "invoice paid"}
    elif event_type == 'invoice.payment_failed':
        return {"status": "invoice payment failed"}
    else:
        return {"status": f"unhandled event: {event_type}"}

# ---------------------------- UTILITY ----------------------------

def handle_checkout_session(session):
    customer_email = session.get('customer_email')
    receipt_email = session.get('receipt_email')
    amount_total = session.get('amount_received', 0)
    amount = float(amount_total) / 100
    product_name = 'Connect Package'

    transaction_data = {
        'email': customer_email or receipt_email,
        'product': product_name,
        'amount': amount,
        'timestamp': str(datetime.now()),
    }

    response = supabase.table("transactions").insert({"data": transaction_data}).execute()

# ---------------------------- ENTRY POINT ----------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
