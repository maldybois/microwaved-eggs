from sqlalchemy import Column, BigInteger, DateTime
from sqlalchemy.sql import func
from .base import Base

# Create a table for user inventories
class UserInventory(Base):
    __tablename__ = 'user_inventory'

    user_id = Column(BigInteger, primary_key=True)
    role_id = Column(BigInteger, primary_key=True)
    quantity = Column(BigInteger)
    inserted_at = Column(DateTime, nullable=False, default=func.now())
