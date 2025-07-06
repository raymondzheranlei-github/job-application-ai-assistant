# Import necessary modules from third-party libraries
from fastapi import FastAPI, UploadFile, Form, File, HTTPException  # Web framework and request handling
import uvicorn                        # ASGI server
import os                             # Operating system utilities
import shutil                         # File operations
import re                             # Regular expressions
import fitz                           # PyMuPDF for PDF parsing
import docx                           # python-docx for DOCX parsing
import openai                         # OpenAI API client
import numpy as np                    # Numerical computations
import resend                         # Resend email service
import yaml                           # YAML parsing
from dotenv import load_dotenv        # Load .env files

# Import database utility functions
from database import (
    init_db,                            # Initialize database tables
    save_application,                   # Save a new application record
    find_application_by_text,           # Lookup by resume text
    find_exact_application_match,       # Lookup by email, resume, and job description
    update_email_status,                # Update email sent status
    log_error,                          # Log errors to DB
)

from fastapi_mcp import add_mcp_server  # MCP server integration

# Load environment variables from .env
load_dotenv()

# Load YAML config into a dict
with open('config.yaml', 'r') as cfg_file:
    config = yaml.safe_load(cfg_file)['project']  # Extract 'project' section

# Set OpenAI API key and default model
openai.api_key = os.getenv('OPENAI_API_KEY')
model_name = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')  

# Ensure database tables exist
init_db()

# Create FastAPI application instance
app = FastAPI(
    title='Job Application Processor API',
    description='API for processing job applications with ChatGPT summaries and OpenAI embeddings.',
    version=config['version'],               # Use version from config
)

# Mount MCP server to enable agentic tool calls
mcp = add_mcp_server(
    app,
    mount_path='/mcp',                       # Path prefix for MCP endpoints
    name='JobApplicationProcessorMCP',       # Name of the MCP service
    description='MCP server for job application processing tools with ChatGPT and OpenAI embeddings.',
    base_url='http://localhost:8000',        # Base URL for callbacks
    describe_all_responses=False,            # Don't auto-describe every response
    describe_full_response_schema=False,     # Don't include full schemas
)

# Define MCP tool: extract text from resume files
@mcp.tool()
def extract_resume_text(file_path: str) -> str:
    """
    Extracts text from PDF or DOCX files at the given path.
    """
    try:
        # PDF: use PyMuPDF
        if file_path.endswith('.pdf'):
            with fitz.open(file_path) as doc:
                text = '\n'.join([page.get_text('text') for page in doc])
        # DOCX: use python-docx
        elif file_path.endswith('.docx'):
            doc = docx.Document(file_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
        else:
            # Unsupported format
            raise ValueError('Unsupported file format. Upload PDF or DOCX.')

        return text.strip()                # Trim whitespace
    except Exception as e:
        log_error(f'Error extracting resume text: {e}')  # Log to DB
        raise

# Define MCP tool: summarize a job description using ChatGPT
@mcp.tool()
def summarize_job_description(job_description_text: str) -> str:
    """
    Generates a concise summary paragraph of the provided job description.
    """
    try:
        # Build system prompt
        prompt = f"""
Create a single, concise paragraph that summarizes ALL key requirements and skills from this job description.
Focus on technical skills, qualifications, experience levels, and essential requirements.
Include specific technologies, tools, education, and experience requirements.
Return ONLY the summary paragraph.
Job Description:
{job_description_text}
"""
        # Call OpenAI ChatCompletion API
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1,              # Low randomness for consistency
        )
        # Return the assistant's summary
        return response.choices[0].message.content.strip()
    except Exception as e:
        log_error(f'Error summarizing job description: {e}')
        return str(e)

# Define MCP tool: compute cosine similarity of embeddings
@mcp.tool()
def score_similarity(resume_text: str, job_summary: str) -> float:
    """
    Calculates a similarity score (0–100) between resume and job summary.
    """
    try:
        # If no summary, zero score
        if not job_summary:
            return 0.0

        # Get embeddings from OpenAI
        resume_embed = openai.Embedding.create(input=resume_text, model='text-embedding-ada-002')
        job_embed = openai.Embedding.create(input=job_summary, model='text-embedding-ada-002')

        # Convert to numpy arrays
        resume_vector = np.array(resume_embed.data[0].embedding)
        job_vector = np.array(job_embed.data[0].embedding)

        # Compute cosine similarity
        similarity = float(
            np.dot(resume_vector, job_vector)
            / (np.linalg.norm(resume_vector) * np.linalg.norm(job_vector))
        )
        # Scale to percentage
        return round(min(100.0, max(0.0, similarity * 100)), 2)
    except Exception as e:
        log_error(f'Error calculating similarity score: {e}')
        return 0.0

# Define MCP tool: extract email from text
@mcp.tool()
def extract_email_address(text: str) -> str:
    """
    Finds and returns the first email address in the given text.
    """
    try:
        match = re.search(r'[\w\.-]+@[\w\.-]+', text)
        return match.group(0) if match else ''
    except Exception as e:
        log_error(f'Error extracting email: {e}')
        return ''

# Define MCP tool: send an email via Resend service
@mcp.tool()
def send_email_notification(recipient_email: str, subject: str, body: str) -> bool:
    """
    Sends a plain-text email using the Resend API.
    """
    try:
        # Configure API key
        resend.api_key = os.getenv('RESEND_API_KEY')
        if not resend.api_key:
            raise ValueError('Resend API key not found')

        # Send the email
        resend.Emails.send({
            'from': 'Your App <onboarding@resend.dev>',
            'to': recipient_email,
            'subject': subject,
            'text': body
        })
        return True
    except Exception as e:
        log_error(f'Error sending email notification: {e}')
        return False

# Define MCP tool: invite candidate if score >= threshold
@mcp.tool()
def invite_for_interview(recipient_email: str, match_score: float) -> bool:
    """
    Sends an interview invite email when candidate meets threshold.
    """
    try:
        # Static booking link
        booking_link = 'https://interview-slot-test.youcanbook.me/'
        subject = 'Interview Invitation - Next Steps'
        body = (
            f'Congratulations! Based on your application review (Match Score: {match_score}%), '
            f'please schedule your interview using the link below:\n{booking_link}'
        )
        # Send and update DB
        if send_email_notification(recipient_email, subject, body):
            update_email_status(recipient_email, True)
            return True
        return False
    except Exception as e:
        log_error(f'Error inviting for interview: {e}')
        return False

# Define MCP tool: check for existing application record
@mcp.tool()
def find_existing_application(resume_text: str):
    """
    Returns (email, score) if a record with identical resume_text exists.
    """
    try:
        app = find_application_by_text(resume_text)
        return (app.email, app.score) if app else (None, None)
    except Exception as e:
        log_error(f'Error finding existing application: {e}')
        return (None, None)

# Define MCP tool: validate document is a resume
@mcp.tool()
def validate_resume_document(text: str) -> bool:
    """
    Uses ChatGPT to confirm text is formatted like a resume/CV.
    """
    try:
        # Build validation prompt
        prompt = f"""
Analyze the following text and determine if it is a resume/CV document.
Return ONLY 'true' or 'false'.
Text:
{text}
"""
        # Call LLM
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip().lower() == 'true'
    except Exception as e:
        log_error(f'Error validating resume: {e}')
        return False

# HTTP POST endpoint: process uploaded resume + job description
@app.post('/applications', tags=['applications'])
async def process_job_application(
    file: UploadFile = File(..., description='Resume file (PDF or DOCX)'),
    job_description_text: str = Form(..., description='Job description to compare')
):
    """
    Main workflow: extract, validate, dedupe, score, invite, and save.
    """
    try:
        # Validate file extension
        if not file.filename.lower().endswith(('.pdf', '.docx')):
            log_error(f'Invalid file format: {file.filename}')
            raise HTTPException(status_code=400, detail='Invalid file format. Only PDF and DOCX are supported.')

        # Save upload locally
        save_dir = 'uploads'
        os.makedirs(save_dir, exist_ok=True)
        resume_path = os.path.join(save_dir, file.filename)
        with open(resume_path, 'wb') as buf:
            shutil.copyfileobj(file.file, buf)

        # Extract and validate resume text
        resume_text = extract_resume_text(resume_path)
        if not validate_resume_document(resume_text):
            log_error('Uploaded document is not a resume')
            raise HTTPException(status_code=400, detail='Uploaded document is not a resume.')

        # Extract candidate email
        email = extract_email_address(resume_text)
        if not email:
            log_error('No email address found in resume')
            raise HTTPException(status_code=400, detail='No email address found in resume.')

        # Check for existing record
        existing = find_exact_application_match(email, resume_text, job_description_text)
        if existing:
            return {
                'email': email,
                'score': existing.score,
                'email_status': existing.email_status,
                'message': 'Existing application retrieved.'
            }

        # Summarize and score
        summary = summarize_job_description(job_description_text)
        match_score = score_similarity(resume_text, summary)

        # Optionally invite candidate
        email_sent = False
        message = 'Candidate did not meet the score threshold.'
        if match_score >= 70:
            message = 'Candidate passed eligibility.'
            email_sent = invite_for_interview(email, match_score)
            message += ' Invitation sent.' if email_sent else ' Failed to send invitation.'

        # Persist result
        save_application(email, resume_text, job_description_text, match_score, email_sent)

        # Return outcome
        return {
            'email': email,
            'score': match_score,
            'email_status': email_sent,
            'message': message
        }
    except HTTPException:
        raise
    except Exception as e:
        # Catch-all error
        log_error(f'Processing error: {e}')
        raise HTTPException(status_code=500, detail='Internal server error.')

# Entry point: run with Uvicorn when invoked directly
if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000)
