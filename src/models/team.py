from sqlalchemy import Column, Integer, String
from src.db.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    abbreviation = Column(String(3), unique=True, index=True)
