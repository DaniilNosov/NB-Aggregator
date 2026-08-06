from pydantic import BaseModel
from datetime import date

class TeamSchema(BaseModel):
    id: int
    name: str
    abbreviation: str

    class Config:
        from_attributes = True

class MatchSchema(BaseModel):
    id: int
    date: date
    home_team: TeamSchema
    away_team: TeamSchema

    class Config:
        from_attributes = True
