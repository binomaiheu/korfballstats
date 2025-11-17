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


## API

The front end application is mounting on the host at `/`, the back-end FastAPI api is mounted under `/api/v1`. Hence, you can access the swagger documentation at : `http://localhost:8855/api/v1/docs`

## Deployment

t.b.a. 

- github actions
- Dockerfile
- digital ocean deploy hook etc...