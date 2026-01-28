# Korfball Player Statistics

This is a webapplication to keep track of korball player statistics. The idea is to be able to manage players, teams and matches and have a handy user interface to increment/decrement number of goals, insides, shots, free-throws, penalies, fouls etc per player/match/team etc.. and as such be able to calculate statistics like shot-percentages per player/team/match. 

The code is written in python using nicegui/fastapi. The backend database is a simple sqlite file. Below are instructions to get started quickly. 

Contact: Bino Maiheu (binomaiheu@gmail.com)

## Getting started

The repo uses `uv` as a python management tool, visit **[this page](https://docs.astral.sh/uv/getting-started/)** for installation instructions. Once you have uv, then simply build the python environment from the project file via `uv sync`. Here are the full commands to clone & install the python dependencies. 

```
git clone git@github.com:binomaiheu/korfballstats.git
cd korfballstats
uv sync
```

Next, source the created environment via 

```bash
source .venv/bin/activate
```

And fire up the app/api via : 

```
python app.py
```

this calls the `uvicorn` ASGI internally. 

Now go to `http://localhost:8855` in your browser to check out the app. 

## Authentication

This app uses username/password authentication. Users cannot self-register; accounts are created manually via a script. All API routes are protected and the UI redirects to `/login` if you're not authenticated.

Create a user:

```
python scripts/create_user.py <username>
```

You will be prompted for a password. After that, login at `http://localhost:8855/login`.

### Environment variables

The following environment variables are used for authentication and storage:

- `KORFBALL_SECRET_KEY`: JWT signing key (required for production)
- `KORFBALL_TOKEN_HOURS`: access token lifetime in hours (default: 12)
- `KORFBALL_STORAGE_SECRET`: NiceGUI storage secret (required for `app.storage.user`)

### Match editing locks

When a user opens a match in the live view, it is locked so only that user can enter actions and update playtime. Locks are released when switching matches/teams or after finalizing.

### Traceability

Actions are stored with the user who submitted them, so match statistics can be traced back to the user.

## Bootstrap data

You can seed teams and players from `teams.yaml` (which links to a players CSV) using:

```
python scripts/bootstrap_db.py
```

If authentication is enabled, provide credentials via:

```
KORFBALL_API_USER=your_user KORFBALL_API_PASSWORD=your_password python scripts/bootstrap_db.py
```

The bootstrap script can also use:

- `KORFBALL_API_URL`: API base URL (default: `http://localhost:8855/api/v1`)
- `KORFBALL_API_USER`: API username
- `KORFBALL_API_PASSWORD`: API password


## API

The front end application is mounting on the host at `/`, the back-end FastAPI api is mounted under `/api/v1`. Hence, you can access the swagger documentation at : `http://localhost:8855/api/v1/docs`

## Deployment

t.b.a. 

- github actions
- Dockerfile
- digital ocean deploy hook etc...