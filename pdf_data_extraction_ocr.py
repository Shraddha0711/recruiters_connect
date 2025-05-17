from fastapi import FastAPI, File, UploadFile, HTTPException
import fitz  # PyMuPDF
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
from openai import OpenAI
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_pdf(pdf_file):
    """Extract text from a PDF file."""
    try:
        pdf_bytes = pdf_file.read()  # Read file bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")  # Open as a stream
        text = "\n".join(page.get_text("text") for page in doc)
        return text.strip()  # Ensure empty pages don't return empty string
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading PDF: {str(e)}")


def extract_text_from_docx(docx_file):
    """Extract text from a DOCX file."""
    try:
        doc = Document(docx_file)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading DOCX: {str(e)}")

def extract_information_from_text(text):
    """Extract structured resume information using OpenAI API."""
    prompt = f"""
    Extract the following information from the given resume text and return a valid JSON object:
    
    {{
        "name": "",
        "city": "",
        "country": "",
        "ctc": float,
        "notice_period": "",
        "linkedin": "",
        "role": "",
        "skills": ["", "", "", ...],
        "experience": float,
        "contact_number": "",
        "email": "",
    }}
    
    Resume Text:
    {text}
    
    Ensure the response is in valid JSON format.
    """

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.2,
    )

    # Convert response to JSON
    extracted_info = response.choices[0].message.content.strip()
    
    try:
        return json.loads(extracted_info)  # Parse string as JSON
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON format in response.")

@app.post("/extract_resume_info/")
async def extract_resume_info(file: UploadFile = File(...)):
    """API endpoint to upload and extract resume information."""
    if file.content_type == "application/pdf":
        text = extract_text_from_pdf(file.file)
    elif file.content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
        text = extract_text_from_docx(file.file)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use PDF or DOCX.")

    extracted_info = extract_information_from_text(text)
    return extracted_info  # Directly return JSON response
