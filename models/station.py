from pydantic import BaseModel, field_validator


class Station(BaseModel):
    stop_id: str
    name: str
    description: str | None = None
    latitude: float
    longitude: float

    @field_validator('latitude', 'longitude', mode='before')
    @classmethod
    def parse_float(cls, v):
        return float(v)


class Line(BaseModel):
    name: str


class StationLine(BaseModel):
    station: Station
    line: Line
    stop_sequence: int

class StationTiming(BaseModel):
    stop_id: str
    line_name: str
    arrival_time: str
    departure_time: str
    date: str
    direction: int
