# CSV Data Viewer

A web application for viewing and searching CSV files containing network data.

## What is CSV Data Viewer?

CSV Data Viewer is a full-stack web application designed to help users view and search CSV files that contain network data. The application allows users to:

- Browse available CSV files
- View the contents of CSV files
- Search for specific MAC addresses within the network data
- Include historical files in searches

The application consists of a React frontend and a FastAPI backend, with data storage using Elasticsearch and task management using Redis and Celery.

## Installation

1.  **Prerequisites:**
    *   [Node.js](https://nodejs.org/) (LTS version)
    *   [Python 3.x](https://www.python.org/)
    *   [Redis](https://redis.io/)
    *   [Elasticsearch](https://www.elastic.co/)

2.  **Backend Setup:**
    ```bash
    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Frontend Setup:**
    ```bash
    cd frontend
    npm install
    ```

4.  **Running the Application:**
    ```bash
    ./start-app.sh
    ```

    This script will start both the backend and frontend servers.

## Available Scripts

In the project directory, you can run:

### `./start-app.sh`

Runs both the backend and frontend servers in development mode.
Open [http://localhost:3000](http://localhost:3000) to view the app in your browser.

The script automatically:
- Activates the Python virtual environment
- Starts the FastAPI backend server
- Starts the React frontend development server
- Provides clean shutdown with Ctrl+C
