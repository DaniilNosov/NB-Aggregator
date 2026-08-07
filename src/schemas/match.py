from pydantic import BaseModel, ConfigDict
from datetime import date

class TeamSchema(BaseModel):
    id: int
    name: str
    abbreviation: str

    model_config = ConfigDict(from_attributes=True)


class MatchSchema(BaseModel):
    id: int
    date: date
    home_team: TeamSchema
    away_team: TeamSchema

    model_config = ConfigDict(from_attributes=True)
