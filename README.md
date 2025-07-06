# job-application-ai-assistant
Leveraged MCP and OpenAPI to implement a multi-agent job application AI assistant 

## Overview

This project is an agentic workflow orchestration system built with the Model Context Protocol (MCP) on FastAPI. It automates job application processing using ChatGPT for job description summarization and OpenAI embeddings for semantic similarity scoring. It also manages email notifications with the Resend API and stores data and error logs in SQLite.

## Features

- **Resume Extraction**   Extracts text from PDF and DOCX files using PyMuPDF and python-docx
- **Job Description Summarization**   Generates concise summaries using ChatGPT (`gpt-3.5-turbo`)
- **Semantic Scoring**   Computes cosine similarity using OpenAI Embeddings (`text-embedding-ada-002`) and numpy
- **Email Automation**   Sends interview invitations via the Resend API for candidates above threshold
- **Duplicate Detection**   Prevents redundant processing by checking existing applications by email, resume, and job description
- **Resume Validation**   Validates documents as resumes using ChatGPT-based analysis
- **Error Logging**   Records errors in a SQLite database for auditing
- **Custom MCP Server**   Exposes tools as reusable endpoints under `/mcp`

## Architecture

1. FastAPI serves as the HTTP server
2. MCP extends FastAPI with agentic tools under `/mcp`
3. Database layer uses SQLAlchemy with SQLite for storage
4. File handling saves uploaded resumes in an `uploads` directory

## Technical Stack

| Component       | Technology            | Purpose                                      |
|-----------------|-----------------------|----------------------------------------------|
| Framework       | FastAPI               | API server                                   |
| MCP             | fastapi-mcp           | Agent orchestration                          |
| Database        | SQLAlchemy, SQLite    | Persistent storage                           |
| NLP             | openai                | ChatGPT summarization and embeddings         |
| Email           | resend                | Notification delivery                        |
| File Processing | PyMuPDF, python-docx  | Resume text extraction                       |
| Utilities       | numpy                 | Numerical operations for similarity scoring  |

## Dependencies

- fastapi
- fastapi-mcp
- uvicorn
- python-dotenv
- openai
- resend
- sqlalchemy
- PyMuPDF
- python-docx
- python-multipart
- numpy

## Usage

1. Obtain API keys for the external services:
   - Sign up at [OpenAI](https://platform.openai.com/) and create an API key for `OPENAI_API_KEY`.
   - Create an account at [Resend](https://resend.com/) to generate a `RESEND_API_KEY`.
2. Copy `.env.example` to `.env` and replace the placeholder values with your own keys. The `.env` file is ignored by Git so your keys remain private.
3. Ensure the `uploads` directory is writable.
4. Run `main.py` to start the API.

## API Endpoints

### POST `/applications`

Processes a job application by analyzing the resume and job description

- **Parameters**  file (PDF or DOCX)  job_description_text
- **Response**  JSON with email, score, email_status, message

## MCP Tools

Tools are available under `/mcp` for individual testing:

- extract_resume_text
- summarize_job_description
- score_similarity
- extract_email_address
- send_email_notification
- invite_for_interview
- find_existing_application
- validate_resume_document

## Database Schema

- applications  id, email, resume_text, job_description, score, email_status, created_at
- error_logs  id, error_message, created_at

## Notes

- Use `OPENAI_API_KEY` for OpenAI access
- Customize the `OPENAI_MODEL` environment variable to switch chat model.
  The sample `.env.example` uses `gpt-4.0` as the default model.
