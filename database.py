# Import SQLAlchemy components and datetime utility
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

# Base class for ORM models
Base = declarative_base()

# Configure module logger
logger = logging.getLogger(__name__)

class Application(Base):
    """ORM model for job applications table"""
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True)          # Auto-increment ID
    email = Column(String, nullable=False)          # Candidate email
    resume_text = Column(Text, nullable=False)      # Full resume text
    job_description = Column(Text, nullable=False)  # Original job description
    score = Column(Float, nullable=False)           # Match score
    email_status = Column(Boolean, default=False)   # Whether an invite was sent
    created_at = Column(DateTime, default=datetime.utcnow)  # Timestamp

class ErrorLog(Base):
    """ORM model for error logs table"""
    __tablename__ = 'error_logs'

    id = Column(Integer, primary_key=True)          # Auto-increment ID
    error_message = Column(Text, nullable=False)    # Error details
    created_at = Column(DateTime, default=datetime.utcnow)  # Timestamp

# SQLite engine and session factory
engine = create_engine('sqlite:///applications.db')    # SQLite database file
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Creates database tables based on ORM models.
    """
    Base.metadata.create_all(bind=engine)

def get_db():
    """
    Dependency generator that yields a DB session and closes it.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_application(email: str, resume_text: str, job_description: str, score: float, email_status: bool = False):
    """
    Inserts a new application record and commits.
    """
    db = SessionLocal()
    try:
        application = Application(
            email=email,
            resume_text=resume_text,
            job_description=job_description,
            score=score,
            email_status=email_status
        )
        db.add(application)   # Stage insert
        db.commit()           # Persist
        return True
    except Exception as e:
        db.rollback()         # Undo on error
        logger.exception('Error saving application')
        log_error(f'Error saving application: {e}')
        return False
    finally:
        db.close()            # Always close session

def find_application_by_text(resume_text: str):
    """
    Returns the first Application with identical resume_text.
    """
    db = SessionLocal()
    try:
        return db.query(Application).filter(Application.resume_text == resume_text).first()
    except Exception as e:
        logger.exception('Error finding application by text')
        log_error(f'Error finding application by text: {e}')
        return None
    finally:
        db.close()

def find_exact_application_match(email: str, resume_text: str, job_description: str):
    """
    Returns an Application matching email, resume_text, and job_description.
    """
    db = SessionLocal()
    try:
        return (
            db.query(Application)
              .filter(
                Application.email == email,
                Application.resume_text == resume_text,
                Application.job_description == job_description
              )
              .first()
        )
    except Exception as e:
        logger.exception('Error finding exact application match')
        log_error(f'Error finding exact application match: {e}')
        return None
    finally:
        db.close()

def update_email_status(email: str, status: bool) -> bool:
    """
    Updates the email_status flag for a given candidate email.
    """
    db = SessionLocal()
    try:
        existing = db.query(Application).filter(Application.email == email).first()
        if existing:
            existing.email_status = status
            db.commit()        # Persist change
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.exception('Error updating email status')
        log_error(f'Error updating email status: {e}')
        return False
    finally:
        db.close()

def log_error(error_message: str):
    """
    Inserts an error log record for auditing.
    """
    db = SessionLocal()
    try:
        log = ErrorLog(error_message=error_message)  # Create log entry
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception('Error logging error message')
    finally:
        db.close()
