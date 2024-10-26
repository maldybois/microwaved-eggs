from sqlalchemy import Column, BigInteger, DateTime
from sqlalchemy.sql import func
from .base import Base

class UserGold(Base):
    __tablename__ = 'user_gold'

    user_id = Column(BigInteger, primary_key=True)
    gold = Column(BigInteger, default=0)
    inserted_at = Column(DateTime, nullable=False, default=func.now())
