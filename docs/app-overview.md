Okay, let's enhance the implementation plan to include environment setup details, models, initial routes, and stubs. This will provide your developers with a more complete starting point, allowing them to begin coding immediately.

**Project: CSV Data Viewer and Search Application**

**Phases:**

*(We'll keep the existing phase breakdown, but with additional details within each phase)*

**Phase 1: Infrastructure and Environment Setup (2 Weeks)**

*   **Goal:** Set up the development environment, server infrastructure, and establish version control.
*   **Tasks:**
    1.  **Server Provisioning:**
 
    2.  **System Dependencies Installation:**
        *   *Action:* Install `git`, `python3.x`, `pip`, `virtualenv`, `nodejs`, `npm`, ``, and any other required OS-level packages, including the redis cli.
        *   *Details:* Use `apt` (or equivalent) to install packages. Install docker and `docker-compose` for future containerization.
        *   *Deliverable:*
            *   Verified installation of required system packages, accessible in the non-root user context.
        *   *Acceptance Criteria:*
            *   `git`, `python3`, `pip`, `virtualenv`, `nodejs`, `npm`, `docker`, `docker-compose`, and `redis-cli` commands are available and functioning.
            *   A non-root user exists.
    3.  **Git Repository Setup:**
        *   *Action:* Create a Git repository on a hosting platform (GitHub, GitLab, Bitbucket).
        *   *Details:*
            *   Follow a Git branching strategy (e.g., Gitflow).
            *   Create `.gitignore` files for both the backend (python) and frontend (javascript).
            *   Add initial `.dockerignore` for both the frontend and the backend.
        *   *Deliverable:*
            *   A remote Git repository with a `develop` and `main` branch.
            *   `.gitignore` files for backend and frontend.
            *   `.dockerignore` file for backend and frontend.
        *   *Acceptance Criteria:*
            *   Developers have access to the repository.
            *   Branching model is documented.
            *   `.gitignore` and `.dockerignore` files are in place for backend and frontend.
    4.  **Virtual Environment Setup:**
        *   *Action:* Create a Python virtual environment for the backend and a Node environment for the frontend.
        *   *Details:*
            *   Use `virtualenv` for Python in the backend (`/backend` folder).
            *   Use `npm` to initialize Node in the frontend (`/frontend` folder).
        *   *Deliverable:*
            *   A working Python virtual environment (`.venv`) within the backend directory, and a `node_modules` directory for the frontend.
        *   *Acceptance Criteria:*
            *   Virtual environments are activated using the corresponding command (`source .venv/bin/activate` for python and `npm install` for Node).

*   **Phase 1 Deliverables:**
    *   Verified installation of required system packages, including docker.
    *   A remote Git repository with the branching strategy documented, as well as the `.gitignore` and `.dockerignore` files.
    *   Working virtual environments for backend and frontend.

**Phase 2: Backend Framework Setup (2 Weeks)**

*   **Goal:** Set up the FastAPI backend, Celery, Redis, basic API endpoints, and initial models.
*   **Tasks:**
    1.  **FastAPI Project Setup:**
        *   *Action:* Create a FastAPI application with a basic project structure.
        *   *Details:*
            *   Include a `main.py` file with the application initialization and settings.
            *   Create a `config.py` file for environment variables and settings.
            *   Create folders to organize code (`/app`, `/api`, `/tasks`, `/utils`).
        *   *Deliverable:*
            *   A basic FastAPI application that can respond to HTTP requests at `/`.
            *   Initial file structure with folder separation.
            *   Initial `config.py` file.
        *   *Acceptance Criteria:*
            *   FastAPI app can run via `uvicorn main:app --reload`.
            *   `/` endpoint responds with a JSON message.
    2.  **Dependency Installation (Backend):**
        *   *Task:* Install required python packages (FastAPI, `uvicorn`, `python-dotenv`, `celery`, `redis`, `elasticsearch`).
        *   *Details:* Use `pip` to install the required libraries within the virtual environment.
        *   *Deliverable:*
            *   All dependencies are installed within the virtual environment.
            *   A `requirements.txt` file with the required packages.
        *   *Acceptance Criteria:*
            *   A list of dependencies are provided in a `requirements.txt` file.
            *   All the packages are installed.
    3.  **Celery Configuration:**
        *   *Task:* Configure Celery to use Redis as a message broker.
        *   *Details:*
            *   Define a `celeryconfig.py` file, a basic task in a file `/tasks/tasks.py`.
            *   Create a task for parsing csv files, logging a message as a stub.
            *   Create an import for celery to be used in `main.py`.
        *   *Deliverable:*
            *   Celery configured and running, connected to Redis.
            *   A stub task created.
        *   *Acceptance Criteria:*
            *   Celery is correctly configured.
            *   Test task can be run by the celery worker and is outputted to the console.
            *   The stub task shows a message on the console.
    4.  **Redis Setup:**
        *   *Task:* Install and run redis.
        *   *Details:* Redis should be running in the server.
        *   *Deliverable:*
            *   Redis installed and running.
        *   *Acceptance Criteria:*
            *   `redis-cli ping` should respond with `PONG`.
    5. **Elasticsearch Setup**
         * *Task:* Create the necessary configuration for ElasticSearch.
         * *Details:* A configuration object should be created that contains the connection details for Elasticsearch.
         * *Deliverable:*
            * A file in /utils/elastic.py with the configuration details
         * *Acceptance Criteria:*
            *   The configuration object is created.
    6.  **Basic CSV file endpoint**
        *   *Task:* Create a basic file endpoint `/api/files` that returns the list of files.
        *   *Details:*
            *   Create a new folder where all the files will be stored `/data`.
            *   The API should return the list of files using a stub for the response (e.g., file names as a string).
            *   Add a new method in `/utils` to extract file names, using stubs and logging statements.
            *    Create a simple BaseModel class that will be used to represent files.
            *    Add a serializer to the model that transforms the file names into an array of dicts with just the file name.
            *   Use `dotenv` to keep environment variables.
            *   **CSV File Source:** The CSV files are named "netspeed.csv" and are located in a specific directory on the server. Each day has a separate file, with "netspeed.csv" representing the most current file, "netspeed.csv.0" representing yesterday's file, and so on.
        *   *Deliverable:*
            *   An endpoint that returns all files inside the `/data` folder as JSON array using stubs.
            *   A new class with a serializer for file representation.
            *  Initial Models Created.
            *   Environment variables loaded with dotenv.
        *   *Acceptance Criteria:*
            *   A call to `/api/files` endpoint should return a json containing all the file names.
            *   The models are ready to be used with a serializer.
            *   The new method returns data that is used in the response.
            *  `.env` file exists with stubs.
    7. **Basic search endpoint**
        *   *Task:* Create a basic `/api/search` endpoint that can receive params.
        *   *Details:*
            *   Create the route with a stub for the main logic.
            *   **Search Modes:** Implement two search modes:
                *   **Normal Search:** Searches the most current "netspeed.csv" file.
                *   **Search All Netspeed Files:** Searches all available "netspeed.csv" files (netspeed.csv, netspeed.csv.0, netspeed.csv.1, etc.).
        *   *Deliverable:*
            *   A stub of the endpoint with a logger.
        *   *Acceptance Criteria:*
            *   The request to `/api/search` should return the logger message.
    8.  **Environment variables setup**
        *   *Task:* Setup environment variables for the project.
        *   *Details:* Add basic variables for the application.
        *   *Deliverable:*
            *   `.env` file with basic environment variables.
        *   *Acceptance Criteria:*
            *   `.env` file exists and can be loaded by python.

*   **Phase 2 Deliverables:**
    *   A basic FastAPI application setup with one endpoint.
    *   Celery and Redis configured and running.
    *   Basic dependency management with pip and `requirements.txt`.
    *   Basic `/api/files` endpoint with initial model created, and serialization of the data, including details about the "netspeed.csv" file source.
    *   Basic `/api/search` endpoint created with stub logic, including implementation of the two search modes.
    *   Initial models created.
    *   Environment variables setup

**Phase 3: Frontend Framework Setup (2 Weeks)**

*   **Goal:** Set up a basic React frontend with Material UI, axios, and a basic table that shows the list of files from the backend.
*   **Tasks:**
    1.  **React Project Setup:**
        *   *Task:* Create a new React project using `create-react-app`.
        *   *Details:* Ensure that the node environment is installed properly. Remove all default files generated.
        *   *Deliverable:*
            *   A basic React app that runs with just an App component in place.
        *   *Acceptance Criteria:*
            *   `npm start` should start the default React development server.
    2.  **Material UI Installation:**
        *   *Task:* Install Material UI and emotion libraries as dependencies.
        *   *Details:* Use `npm` to install the dependencies in the frontend folder.
        *   *Deliverable:*
            *   Material UI dependencies added to `package.json`.
        *   *Acceptance Criteria:*
            *   Material UI components can be imported and rendered in React components.
    3.  **Axios Installation:**
        *   *Task:* Install the `axios` library.
        *   *Details:* Use `npm` to install the `axios` dependency.
        *   *Deliverable:*
            *   `axios` dependency installed.
        *   *Acceptance Criteria:*
            *   `axios` can be used to make HTTP requests.
    4.  **Basic Table Component:**
        *   *Task:* Create a basic table component in React, in a new `Components` folder.
        *   *Details:*
            *   Use Material UI components for table rendering.
            *   Include logic to call the backend `/api/files` endpoint using `axios`.
            *   Create a custom hook in `/hooks` that handles the fetch of the files.
        *   *Deliverable:*
            *   A basic table component that renders the list of files fetched from the backend.
            *   A custom hook is created and used to fetch the data.
        *   *Acceptance Criteria:*
            *   Table should display the file names returned from the `/api/files` endpoint.
            *   The custom hook is used to manage the fetch logic.

*   **Phase 3 Deliverables:**
    *   A basic React app with a running dev server.
    *   Material UI installed and ready to be used.
    *   Axios is ready to be used.
    *   A basic table component that shows the list of files.

**Phase 4: Elasticsearch Setup (1 Week)**

*   **Goal:** Install and configure Elasticsearch for data indexing and querying.
*   **Tasks:**
    1.  **Elasticsearch Installation:**
        *   *Task:* Install Elasticsearch on the server.
        *   *Details:* Use the official documentation from elastic.
        *   *Deliverable:*
            *   A running Elasticsearch instance in the server.
        *   *Acceptance Criteria:*
            *   A call to Elasticsearch using curl returns data.
    2.  **Elasticsearch Testing (Python)**
        *   *Task:* Create a python script that connects to Elasticsearch to test it.
        *   *Details:* A simple python script that reads/writes a test document to Elasticsearch using the configuration created in Phase 2.
        *   *Deliverable:*
            *   A script that writes and retrieves the test document.
        *   *Acceptance Criteria:*
            *   The test script inserts and gets the test document.

*   **Phase 4 Deliverables:**
    *   A running Elasticsearch instance.
    *   A working python test script that proves Elasticsearch is working.

**Important Notes for Developers:**

*   All API endpoints in the backend should be created within a `/api` folder using the FastAPI `APIRouter` class.
*   All Models should be created in a `models` folder.
*   All helper methods should be in the `/utils` folder
*   Ensure that your code respects the project structure created in each phase.
*   Follow the logging conventions created.
*   Use the stubs that were created for each component as a starting point.
