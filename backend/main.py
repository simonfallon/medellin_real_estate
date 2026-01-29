from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
from . import database, scraper, storage
from .scrapers.base import ScraperConfig
from datetime import datetime, timedelta

app = FastAPI()

last_scrape_time = None
SCRAPE_COOLDOWN_MINUTES = 120

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Create engine if not exists (db init is already called)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/api/properties")
def read_properties(
    skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)
):
    properties = (
        db.query(database.Property)
        .filter(database.Property.deleted_at == None)
        .order_by(database.Property.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return properties


@app.get("/api/properties/locations")
def read_property_locations(db: Session = Depends(database.get_db)):
    # Fetch only necessary fields for the map to be efficient
    # Filter out properties without coordinates
    properties = (
        db.query(
            database.Property.id,
            database.Property.latitude,
            database.Property.longitude,
            database.Property.title,
            database.Property.price,
            database.Property.source,
            database.Property.link,
            database.Property.image_url,
            database.Property.location,
            database.Property.location,
            database.Property.code,
            database.Property.images,
        )
        .filter(database.Property.latitude != None, database.Property.longitude != None)
        .filter(database.Property.deleted_at == None)
        .all()
    )

    # Convert to list of dicts since query returns tuples
    return [
        {
            "id": p.id,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "title": p.title,
            "price": p.price,
            "source": p.source,
            "link": p.link,
            "image_url": p.image_url,
            "location": p.location,
            "code": p.code,
            "images": p.images,
        }
        for p in properties
    ]


@app.post("/api/scrape/batch")
async def trigger_batch_scrape(
    source: str = "all",
    force: bool = False,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    db: Session = Depends(database.get_db),
):
    global last_scrape_time
    try:
        now = datetime.now()
        if (
            not force
            and last_scrape_time
            and (now - last_scrape_time) < timedelta(minutes=SCRAPE_COOLDOWN_MINUTES)
        ):
            return {
                "message": f"Data is fresh. Last updated: {last_scrape_time.strftime('%H:%M:%S')}",
                "new_properties": 0,
                "total_found": 0,
                "cached": True,
            }

        # Build custom config if prices provided
        custom_config = None
        if price_min is not None and price_max is not None:
            # Validation
            if price_min < 0 or price_max < 0:
                raise HTTPException(status_code=400, detail="Prices must be positive")
            if price_min >= price_max:
                raise HTTPException(
                    status_code=400, detail="Min price must be less than max price"
                )
            if price_max > 50000000:  # 50M COP sanity check
                raise HTTPException(
                    status_code=400, detail="Max price exceeds reasonable limit"
                )

            custom_config = ScraperConfig(
                price_ranges=[{"min": price_min, "max": price_max}]
            )

        # Pass config to scraper functions
        if source == "alberto_alvarez":
            data = await scraper.scrape_alberto_alvarez_batch(custom_config)
        elif source == "arrendamientos_envigado":
            data = await scraper.scrape_arrendamientos_envigado_batch(custom_config)
        elif source == "proteger":
            data = await scraper.scrape_proteger_batch(custom_config)
        elif source == "arrendamientos_las_vegas":
            data = await scraper.scrape_arrendamientos_las_vegas_batch(custom_config)
        elif source == "escala_inmobiliaria":
            data = await scraper.scrape_escala_inmobiliaria_batch(custom_config)
        elif source == "uribienes":
            data = await scraper.scrape_uribienes_batch(custom_config)
        elif source == "livinmobiliaria":
            data = await scraper.scrape_livinmobiliaria_batch(custom_config)
        else:
            data = await scraper.scrape_all_batch(custom_config)

        last_scrape_time = datetime.now()
        return storage.save_properties(db, data)
    except HTTPException:
        # Re-raise HTTPException as-is (validation errors, etc.)
        raise
    except Exception as e:
        # Catch all other exceptions and return 500
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return FileResponse("frontend/index.html")
