# FastAPI File Echo API

This API accepts an Excel or CSV file upload and returns the same file as a response. Each upload is logged in a SQLite database.

## Features
- Upload CSV or Excel files
- Returns the same file as a download
- Logs each upload (filename, timestamp) in SQLite

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   uvicorn main:app --reload
   ```
3. Visit [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs.

## API Usage

- **POST** `/upload`
  - Form-data: `file` (CSV or Excel file)
  - Response: The same file as an attachment

## Deployment (Render)

1. Push this repo to GitHub.
2. Go to [https://render.com/](https://render.com/) and create a new Web Service.
3. Connect your GitHub repo.
4. Set the build and start commands:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 10000`
5. Choose a free plan and deploy.

## Notes
- The SQLite database (`uploads.db`) will persist only as long as the deployment instance is alive (ephemeral on free plans).
- No caching is used, as the API simply echoes the uploaded file. 