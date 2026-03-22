from dataclasses import dataclass

@dataclass
class Station:
    """Modèle représentant une station"""
    name: str # 50 caractères max
    address: str # 100 caractères max
    line: str 
    latitude: float
    longitude: float
