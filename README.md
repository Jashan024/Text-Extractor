# Text Extractor

A Flask web application that extracts **names**, **locations**, and **job titles** from structured profile/resume text data — no API keys required.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-green?logo=flask&logoColor=white)
![spaCy](https://img.shields.io/badge/spaCy-3.7-09a3d5?logo=spacy&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Smart Parsing** — Structure-aware, line-by-line parser that handles duplicate headers, section markers, education blocks, certifications, and employer metadata
- **Stat Dashboard** — Animated counter cards showing total people, locations, and unique titles extracted
- **CSV Export** — One-click download of all extracted data as a CSV file
- **Modern UI** — Clean, responsive design with Google Inter font, SVG icons, and smooth animations
- **Keyboard Shortcut** — `Ctrl + Enter` to extract instantly
- **Production Ready** — Gunicorn support, health-check endpoint, error handlers, and configurable via environment variables

## Quick Start

### Prerequisites

- Python 3.10+

### Installation

```bash
# Clone the repo
git clone https://github.com/Jashan024/Text-Extractor.git
cd Text-Extractor

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model
python -m spacy download en_core_web_sm
```

### Run Locally

```bash
# Development mode
python app.py

# OR with Gunicorn (production)
gunicorn app:app --bind 0.0.0.0:5000 --workers 2
```

Open **http://localhost:5000** in your browser.

## Usage

1. Paste structured profile text into the text area
2. Click **Extract Data** (or press `Ctrl + Enter`)
3. View extracted data in the results table
4. Click **Download CSV** to export the data

### Expected Input Format

```
John Smith
John Smith
Pittsburgh, PA
Relevant Work Experience
Senior Software Engineer
Google, 2021 - Present
Software Engineer
Microsoft, 2018 - 2021
Education
B.S. Computer Science
```

## Project Structure

```
Text-Extractor/
├── app.py                 # Flask server & routes
├── extractor.py           # Text parsing engine
├── requirements.txt       # Python dependencies
├── Procfile               # Gunicorn config for deployment
├── runtime.txt            # Python version for deployment
├── templates/
│   └── index.html         # Frontend UI
└── static/
    └── style.css          # Stylesheet
```

## API Endpoints

| Method | Endpoint    | Description                         |
|--------|-------------|-------------------------------------|
| GET    | `/`         | Serve the web UI                    |
| POST   | `/extract`  | Extract entities from text (JSON)   |
| GET    | `/health`   | Health check for monitoring         |

### POST `/extract`

**Request:**
```json
{
  "text": "John Smith\nJohn Smith\nPittsburgh, PA\nRelevant Work Experience\nSenior Engineer\nGoogle, 2021 - Present"
}
```

**Response:**
```json
{
  "names": ["John Smith"],
  "locations": ["Pittsburgh, PA"],
  "titles": ["Senior Engineer"],
  "people": [
    {
      "name": "John Smith",
      "location": "Pittsburgh, PA",
      "titles": ["Senior Engineer"]
    }
  ]
}
```

## Deployment

The app is deployment-ready for platforms like **Render**, **Railway**, **Heroku**, or **Fly.io**.

### Environment Variables

| Variable    | Default       | Description             |
|-------------|---------------|-------------------------|
| `PORT`      | `5000`        | Server port             |
| `FLASK_ENV` | `production`  | Set to `development` for debug mode |

## License

MIT
