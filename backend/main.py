from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import database, scraper, storage
import threading
import asyncio
from pydantic import BaseModel
from datetime import datetime, timedelta
import json

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
import os

# Create engine if not exists (db init is already called)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/api/properties")
def read_properties(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    properties = db.query(database.Property).offset(skip).limit(limit).all()
    return properties



@app.post("/api/scrape/batch")
async def trigger_batch_scrape(source: str = "all", force: bool = False, db: Session = Depends(database.get_db)):
    global last_scrape_time
    try:
        now = datetime.now()
        if not force and last_scrape_time and (now - last_scrape_time) < timedelta(minutes=SCRAPE_COOLDOWN_MINUTES):
            return {
                "message": f"Data is fresh. Last updated: {last_scrape_time.strftime('%H:%M:%S')}", 
                "new_properties": 0, 
                "total_found": 0,
                "cached": True
            }
            
        if source == "alberto_alvarez":
            data = await scraper.scrape_alberto_alvarez_batch()
        elif source == "arrendamientos_envigado":
            data = await scraper.scrape_arrendamientos_envigado_batch()
        elif source == "proteger":
            data = await scraper.scrape_proteger_batch()
        else:
            data = await scraper.scrape_all_batch()
            
        last_scrape_time = datetime.now()
        return storage.save_properties(db, data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return FileResponse('frontend/index.html')
