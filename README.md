# 🏠 Sherlock Homes - Premium Medellin Real Estate Finder

A powerful web scraping and property aggregation platform for finding rental apartments in Medellín, Colombia. This application automatically scrapes multiple real estate websites, aggregates listings, and presents them in a beautiful, filterable interface.

![Sherlock Homes](./alberto_alvarez_single.png)

## ✨ Features

- 🔍 **Automated Web Scraping**: Scrapes multiple real estate websites simultaneously
- 🎯 **Smart Filtering**: Filter by price, area, bedrooms, bathrooms, and parking
- 📊 **Multiple Sorting Options**: Sort by price, area, or date added
- 🏘️ **Neighborhood Focus**: Targets premium neighborhoods in Envigado
- 💾 **SQLite Database**: Stores and deduplicates property listings
- 🎨 **Modern UI**: Beautiful, responsive interface with smooth animations
- ⚡ **Real-time Updates**: Live scraping with progress indicators
- 🔄 **Smart Caching**: Prevents excessive scraping with 2-hour cooldown

## 🎯 Supported Websites

1. **Arrendamientos Envigado** - Local real estate agency
2. **Alberto Álvarez** - Premium real estate agency

## 🏘️ Targeted Neighborhoods

The scraper focuses on premium neighborhoods in Envigado:
- El Portal
- Jardines
- La Abadia
- La Frontera
- La Magnolia
- Las Flores
- Las Vegas
- Loma Benedictinos
- Pontevedra
- San Marcos
- Villagrande
- Zuñiga
- Otra Parte

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Internet connection for scraping

## 🚀 Installation

### 1. Clone or Download the Repository

```bash
cd /path/to/medellin_real_estate
```

### 2. Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv backend/venv

# Activate virtual environment
# On macOS/Linux:
source backend/venv/bin/activate

# On Windows:
# backend\venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Install Playwright Browsers

Playwright requires browser binaries to be installed:

```bash
playwright install chromium
```

## 🎮 Usage

### Starting the Application

#### Option 1: Using Uvicorn Directly

```bash
# Make sure you're in the project root directory
cd /Users/simon/.gemini/antigravity/scratch/medellin_real_estate

# Start the server
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

#### Option 2: Using the Run Script

```bash
python3 run_scraper.py
```

### Accessing the Application

Once the server is running, open your browser and navigate to:

```
http://localhost:8000
```

## 🔧 How to Use the Interface

### 1. **Initial Load**
- The app will display any previously scraped properties from the database
- If this is your first time, the database will be empty

### 2. **Scraping Properties**

**Select a Source:**
- Choose from the dropdown: "Arrendamientos Envigado", "Alberto Álvarez", or "Todos" (All)

**Force Update (Optional):**
- Check "Forzar actualización" to bypass the 2-hour cache
- Leave unchecked to use cached data if available

**Click "Buscar Propiedades":**
- The scraper will start collecting properties
- A notification will show progress
- Properties will appear in the grid as they're found

### 3. **Filtering Properties**

Use the filter panel on the left to narrow down results:

- **Precio Mínimo/Máximo**: Set price range (in COP)
- **Área Mínima/Máxima**: Filter by square meters
- **Habitaciones**: Minimum/maximum bedrooms
- **Parqueaderos**: Minimum parking spaces

Filters apply in real-time as you type!

### 4. **Sorting Results**

Use the sort dropdown to organize properties:
- Más Recientes (Most Recent)
- Precio: Menor a Mayor (Price: Low to High)
- Precio: Mayor a Menor (Price: High to Low)
- Área: Menor a Mayor (Area: Small to Large)
- Área: Mayor a Menor (Area: Large to Small)

### 5. **Viewing Property Details**

Click "Ver Propiedad" on any card to open the original listing in a new tab.

## 🗂️ Project Structure

```
medellin_real_estate/
├── backend/
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── alberto_alvarez.py      # Alberto Álvarez scraper
│   │   └── arrendamientos_envigado.py  # Arrendamientos Envigado scraper
│   ├── database.py                  # SQLAlchemy models and DB setup
│   ├── main.py                      # FastAPI application
│   ├── scraper.py                   # Scraper orchestration
│   └── requirements.txt             # Python dependencies
├── frontend/
│   ├── index.html                   # Main UI
│   ├── styles.css                   # Styling
│   └── script.js                    # Frontend logic
├── real_estate.db                   # SQLite database (auto-created)
├── run_scraper.py                   # Convenience script
└── README.md                        # This file
```

## 🛠️ Configuration

### Modifying Search Parameters

#### Price Ranges (Arrendamientos Envigado)

Edit `backend/scrapers/arrendamientos_envigado.py`:

```python
PRICE_RANGES = [
    {"min": 2500000, "max": 3500000}  # Add more ranges as needed
]
```

#### Bedrooms Filter (Alberto Álvarez)

Edit `backend/scrapers/alberto_alvarez.py`:

```python
SEARCH_URLS = [
    "https://albertoalvarez.com/inmuebles/arrendamientos/apartamento/envigado/?roomsFrom=1&roomsTo=2"
]
```

Change `roomsFrom` and `roomsTo` parameters as needed.

### Adding New Neighborhoods

Edit the `BARRIOS` dictionary in either scraper file:

```python
BARRIOS = {
    "New Neighborhood": "url-slug-or-id",
    # ... existing neighborhoods
}
```

## 🐛 Troubleshooting

### "Command not found: uvicorn"

Make sure you've activated the virtual environment:

```bash
source backend/venv/bin/activate
```

Then install dependencies:

```bash
pip install -r backend/requirements.txt
```

### Scraper Not Finding Properties

1. Check your internet connection
2. Verify the target websites are accessible
3. The websites may have changed their HTML structure (requires scraper updates)
4. Try using "Forzar actualización" to bypass cache

### Database Issues

If you encounter database errors, you can reset it:

```bash
rm real_estate.db
# Restart the application - it will create a fresh database
```

### Playwright Browser Issues

Reinstall Playwright browsers:

```bash
playwright install --force chromium
```

## 🔒 Rate Limiting & Ethics

- The app includes a 2-hour cooldown between scrapes to be respectful to target websites
- Scraping is done with reasonable delays between requests
- Always respect robots.txt and terms of service of target websites
- This tool is for personal use and research purposes

## 📊 Database Schema

The SQLite database stores properties with the following fields:

- `id`: Primary key
- `code`: Property reference code
- `title`: Property title
- `location`: Neighborhood/location
- `price`: Monthly rent price
- `area`: Square meters
- `bedrooms`: Number of bedrooms
- `bathrooms`: Number of bathrooms
- `parking`: Number of parking spaces
- `estrato`: Socioeconomic stratum
- `image_url`: Main property image
- `link`: URL to original listing
- `source`: Website source
- `created_at`: Timestamp when added

## 🚀 Advanced Usage

### Running Scrapers Programmatically

You can import and run scrapers directly:

```python
import asyncio
from backend.scrapers import alberto_alvarez, arrendamientos_envigado

# Run a specific scraper
async def main():
    results = await alberto_alvarez.scrape()
    print(f"Found {len(results)} properties")

asyncio.run(main())
```

### API Endpoints

The FastAPI backend exposes these endpoints:

- `GET /` - Serves the frontend
- `GET /api/properties?skip=0&limit=100` - Get properties from database
- `POST /api/scrape/batch?source=all&force=false` - Trigger batch scraping

## 📝 License

This project is for educational and personal use only. Respect the terms of service of all scraped websites.

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

## 📧 Support

For issues or questions, please check the troubleshooting section above.

---

**Happy House Hunting! 🏡**
