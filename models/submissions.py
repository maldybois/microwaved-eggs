from sqlalchemy import Column, BigInteger, DateTime
from sqlalchemy.sql import func
from .base import Base

# Create a table to track submissions
class Submission(Base):
    __tablename__ = 'submissions'

    user_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, primary_key=True)
    inserted_at = Column(DateTime, nullable=False, default=func.now())