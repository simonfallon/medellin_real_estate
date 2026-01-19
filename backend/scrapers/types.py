from typing import TypedDict, List, Optional

class Property(TypedDict):
    code: str
    title: str
    location: str
    price: str
    area: str
    estrato: str
    bedrooms: str
    bathrooms: str
    parking: str
    description: Optional[str]
    images: List[str]
    image_url: Optional[str]
    link: str
    source: str
    latitude: Optional[float]
    longitude: Optional[float]
