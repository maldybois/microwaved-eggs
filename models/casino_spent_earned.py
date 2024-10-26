from sqlalchemy import Column, BigInteger, DateTime
from sqlalchemy.sql import func
from .base import Base

# Create a table to track submissions
class CasinoSpentEarned(Base):
    __tablename__ = 'casino_spent_earned'

    user_id = Column(BigInteger, primary_key=True)
    total_spent = Column(BigInteger, nullable=False)  # total of cost to play
    total_earned = Column(BigInteger, nullable=False)  # earned + cost to play