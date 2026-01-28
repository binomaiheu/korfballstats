#!/usr/bin/env python3
import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml


DEFAULT_BASE_URL = "http://localhost:8855/api/v1"
AUTH_TOKEN: str | None = None


def http_json(method: str, path: str, payload: dict | None = None) -> Any:
    base_url = os.getenv("KORFBALL_API_URL", DEFAULT_BASE_URL).rstrip("/")
    url = f"{base_url}{path}"
    headers = {}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    response = requests.request(method, url, json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    if not response.content:
        return None
    return response.json()


def safe_post(path: str, payload: dict) -> Any:
    try:
        return http_json("POST", path, payload)
    except requests.HTTPError as exc:
        response = exc.response
        detail = None
        if response is not None and response.content:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
        raise RuntimeError(f"POST {path} failed: {response.status_code if response else ''} {detail}") from exc


def login(username: str, password: str) -> None:
    global AUTH_TOKEN
    data = safe_post("/auth/login", {"username": username, "password": password})
    AUTH_TOKEN = data.get("access_token")
    if not AUTH_TOKEN:
        raise RuntimeError("Login failed: no access token returned")


def fetch_list(path: str) -> list[dict]:
    try:
        data = http_json("GET", path)
        return data if isinstance(data, list) else []
    except requests.RequestException as exc:
        raise RuntimeError(f"GET {path} failed: {exc}") from exc


def find_team(existing: Iterable[dict], name: str) -> dict | None:
    for team in existing:
        if team.get("name") == name:
            return team
    return None


def find_player(existing: Iterable[dict], player: dict) -> dict | None:
    for item in existing:
        if (
            item.get("first_name") == player.get("first_name")
            and item.get("last_name") == player.get("last_name")
        ):
            return item
    return None


def ensure_team(existing: list[dict], name: str) -> dict:
    found = find_team(existing, name)
    if found:
        return found
    created = safe_post("/teams", {"name": name})
    existing.append(created)
    return created


def ensure_player(existing: list[dict], player: dict) -> dict:
    found = find_player(existing, player)
    if found:
        return found
    created = safe_post("/players", player)
    existing.append(created)
    return created


def assign_player(team_id: int, player_id: int) -> None:
    try:
        safe_post("/teams/assign", {"team_id": team_id, "player_id": player_id})
    except RuntimeError as exc:
        message = str(exc)
        if "already assigned" not in message:
            raise


def parse_teams_yaml(path: Path) -> tuple[Path, list[dict]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError("teams.yaml must contain a mapping")

    players_csv = data.get("players")
    if not players_csv:
        raise RuntimeError("teams.yaml is missing a 'players:' entry")

    teams = data.get("teams")
    if not isinstance(teams, list):
        raise RuntimeError("teams.yaml is missing a 'teams:' list")

    normalized = []
    for team in teams:
        if not isinstance(team, dict):
            raise RuntimeError("Each team entry must be a mapping")
        name = team.get("name")
        if not name:
            raise RuntimeError("Each team entry must include a name")
        players = team.get("players", [])
        if not isinstance(players, list):
            raise RuntimeError(f"Team '{name}' players must be a list")
        normalized.append({"name": name, "players": [int(num) for num in players]})

    return (path.parent / str(players_csv)).resolve(), normalized


def load_players_csv(path: Path) -> list[dict]:
    players = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if len(row) < 4:
                raise RuntimeError(f"Invalid row in players CSV: {row}")
            first_name, last_name, number, sex = [part.strip() for part in row[:4]]
            players.append(
                {
                    "number": int(number),
                    "first_name": first_name,
                    "last_name": last_name,
                    "sex": sex,
                }
            )
    return players


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap teams and players via API.")
    parser.add_argument(
        "--teams",
        default="teams.yaml",
        help="Path to teams.yaml (default: teams.yaml)",
    )
    parser.add_argument("--username", help="API username (or set KORFBALL_API_USER)")
    parser.add_argument("--password", help="API password (or set KORFBALL_API_PASSWORD)")
    args = parser.parse_args()

    teams_path = Path(args.teams).resolve()
    players_csv_path, teams = parse_teams_yaml(teams_path)
    players = load_players_csv(players_csv_path)

    username = args.username or os.getenv("KORFBALL_API_USER")
    password = args.password or os.getenv("KORFBALL_API_PASSWORD")
    if username and password:
        login(username, password)

    existing_teams = fetch_list("/teams")
    existing_players = fetch_list("/players")

    team_ids = {}
    for team in teams:
        team_name = team["name"]
        created_team = ensure_team(existing_teams, team_name)
        team_ids[team_name] = created_team["id"]

    player_ids = {}
    for player in players:
        created = ensure_player(existing_players, player)
        player_ids[player["number"]] = created["id"]

    for team in teams:
        team_id = team_ids[team["name"]]
        for number in team["players"]:
            player_id = player_ids.get(number)
            if not player_id:
                raise RuntimeError(f"Player number {number} not found in players CSV")
            assign_player(team_id, player_id)

    print("Bootstrap complete.")


if __name__ == "__main__":
    main()
