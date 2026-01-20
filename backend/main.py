from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import database, scraper, storage
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
    source: str = "all", force: bool = False, db: Session = Depends(database.get_db)
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

        if source == "alberto_alvarez":
            data = await scraper.scrape_alberto_alvarez_batch()
        elif source == "arrendamientos_envigado":
            data = await scraper.scrape_arrendamientos_envigado_batch()
        elif source == "proteger":
            data = await scraper.scrape_proteger_batch()
        elif source == "arrendamientos_las_vegas":
            data = await scraper.scrape_arrendamientos_las_vegas_batch()
        elif source == "escala_inmobiliaria":
            data = await scraper.scrape_escala_inmobiliaria_batch()
        elif source == "uribienes":
            data = await scraper.scrape_uribienes_batch()
        else:
            data = await scraper.scrape_all_batch()

        last_scrape_time = datetime.now()
        return storage.save_properties(db, data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return FileResponse("frontend/index.html")
