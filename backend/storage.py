import json
from . import database
import re
import math

ENVIGADO_PARK_COORDS = (6.170089, -75.587481)
MAX_DISTANCE_KM = 10


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
        math.radians(lat1)
    ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_price(price_str):
    if not price_str:
        return 0
    # Remove everything except digits
    digits = re.sub(r"[^\d]", "", str(price_str))
    try:
        return int(digits)
    except:
        return 0


def save_properties(db, properties_list):
    """
    Saves a list of property dictionaries to the database.
    Handles deduplication and updates existing records.
    Returns a dict with statistics.
    """
    count = 0
    # Deduplicate input data based on link
    unique_data = {item["link"]: item for item in properties_list}.values()

    # Get model columns
    model_columns = {c.name for c in database.Property.__table__.columns}

    for item in unique_data:
        # Filter by location (max 10km from Envigado Park)
        lat_raw = item.get("latitude")
        lon_raw = item.get("longitude")
        if lat_raw is not None and lon_raw is not None:
            try:
                lat = float(lat_raw)
                lon = float(lon_raw)
                # Filter by distance from Envigado Park
                if (
                    calculate_distance(lat, lon, *ENVIGADO_PARK_COORDS)
                    > MAX_DISTANCE_KM
                ):
                    item["latitude"] = None
                    item["longitude"] = None
            except (ValueError, TypeError):
                pass

        # Check duplicates
        existing = (
            db.query(database.Property)
            .filter(database.Property.link == item["link"])
            .first()
        )

        if not existing:
            # Map fields
            db_item = item.copy()
            # Handle images list if present
            if "images" in db_item:
                images_list = db_item["images"]
                if images_list and len(images_list) > 0:
                    db_item["image_url"] = images_list[0]
                    # Ensure it is stored as JSON string
                    if isinstance(images_list, list):
                        db_item["images"] = json.dumps(images_list)
                else:
                    db_item["images"] = "[]"

            # Filter only keys that exist in model
            filtered_item = {k: v for k, v in db_item.items() if k in model_columns}

            prop = database.Property(**filtered_item)
            db.add(prop)
            count += 1
        else:
            # Update existing record
            existing.location = item.get("location", existing.location)
            existing.title = item.get("title", existing.title)
            # existing.image_url = item.get('image_url', existing.image_url) # Logic in run_scraper was more complex for images

            # Update images logic matching run_scraper more closely but cleaner
            if "images" in item and item["images"]:
                images_list = item["images"]
                existing.image_url = images_list[0]
                existing.images = json.dumps(images_list)
            elif item.get("image_url"):
                existing.image_url = item.get("image_url")

            existing.code = item.get("code", existing.code)
            existing.price = item.get("price", existing.price)
            existing.area = item.get("area", existing.area)
            existing.bedrooms = item.get("bedrooms", existing.bedrooms)
            existing.bathrooms = item.get("bathrooms", existing.bathrooms)
            existing.parking = item.get("parking", existing.parking)
            existing.estrato = item.get("estrato", existing.estrato)
            existing.latitude = item.get("latitude", existing.latitude)
            existing.longitude = item.get("longitude", existing.longitude)
            # Update timestamp
            # existing.updated_at = datetime.utcnow() # SQLAlchemy handles this with onupdate

    db.commit()
    return {
        "message": "Batch saving completed",
        "new_properties": count,
        "total_processed": len(unique_data),
        "total_input": len(properties_list),
    }
