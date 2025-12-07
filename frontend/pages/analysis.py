from asyncio import events
import logging
from collections import defaultdict

from nicegui import ui, events

from backend.schema import ActionType
from frontend.api import api_get, api_post
from frontend.layout import apply_layout

from typing import Dict, List, Optional

logger = logging.getLogger('uvicorn.error')


@ui.page('/analysis')
def analysis_page():

    def content():

        # ----------------------------------------------------------------------
        # HELPERS
        # ----------------------------------------------------------------------

        async def load_teams():
            teams = await api_get("/teams")
            team_select.set_options({t["id"]: t["name"] for t in teams})

        async def load_matches(team_id=None):
            """Load matches. If team_id is given: filter only that team's matches."""
            if team_id:
                matches = await api_get(f"/teams/{team_id}/matches")
            else:
                matches = await api_get("/matches")

            match_select.set_options({
                m["id"]: f'{m.get("date", "")[:10]} — {m.get("opponent_name", "")} ({m["team"]["name"]})'
                for m in matches
            })

            match_select.value = None  # reset

        # ----------------------------------------------------------------------
        # MAIN STATS LOADER
        # ----------------------------------------------------------------------

        async def load_statistics(match_id: int):
            if not match_id:
                return

            # Fetch actions for this match
            match = await api_get(f"/matches/{match_id}")
            logger.info(match)
            # Fetch match info so we know the team → players
            players = await api_get(f"/teams/{match['team']['id']}/players")

            # get the actions
            actions = await api_get(f"/matches/{match_id}/actions")

            # Prepare stats structure
            stats = defaultdict(lambda: {
                "name": "",
                "number": "",
                "totals": {a.value: 0 for a in ActionType},
                "success": 0,
                "attempts": 0,
            })

            # Initialize players in stats
            for p in players:
                stats[p["id"]]["name"] = f"{p['first_name']} {p['last_name']}"
                stats[p["id"]]["number"] = p["number"]

            # Count actions
            for a in actions:
                pid = a["player_id"]
                if pid not in stats:
                    continue  # safety

                stats[pid]["totals"][a["action"]] += 1

                if a["action"] in {ActionType.SHOT, ActionType.KORTE_KANS,
                                   ActionType.VRIJWORP, ActionType.STRAFWORP,
                                   ActionType.INLOPER}:
                    stats[pid]["attempts"] += 1
                    if a["result"]:
                        stats[pid]["success"] += 1

            # Convert to table rows
            table_rows = []
            for pid, s in stats.items():
                row = {
                    "player": s["name"],
                    "nr": s["number"],
                    **s["totals"],
                    "goals": s["success"],
                    "efficiency":
                        f"{round(100 * s['success'] / s['attempts'], 1)}%"
                        if s["attempts"] else "-",
                }
                table_rows.append(row)

            stats_table.rows = table_rows


        # ----------------------------------------------------------------------
        # EVENT HANDLERS
        # ----------------------------------------------------------------------

        async def on_team_change(team_id):
            await load_matches(team_id)

        async def on_match_change(match_id):
            logger.info(f"Selected match ID: {match_id}")
            await load_statistics(match_id)


        # ----------------------------------------------------------------------
        # UI LAYOUT
        # ----------------------------------------------------------------------

        ui.markdown("### 🏷️ Analysis")

        with ui.row().classes("items-center gap-4"):
            team_select = ui.select(
                {},
                label="Select team",
                with_input=False,
                on_change=lambda e: on_team_change(e.value),
            ).classes("w-32")

            match_select = ui.select(
                {},
                label="Select match",
                with_input=False,
                on_change=lambda e: on_match_change(e.value),
            ).classes("w-48")

        ui.separator()

        # Player statistics table
        columns = [
            {"name": "player", "label": "Player", "field": "player"},
            {"name": "nr", "label": "Nr", "field": "nr"},
        ] + [
            {"name": a.value, "label": a.value.replace("_", " ").title(), "field": a.value}
            for a in ActionType
        ] + [
            {"name": "goals", "label": "Goals", "field": "goals"},
            {"name": "efficiency", "label": "Efficiency", "field": "efficiency"},
        ]

        stats_table = ui.table(
            columns=columns,
            rows=[],
            pagination=20,
            row_key="player",
        ).classes("w-full")

        # ----------------------------------------------------------------------
        # INITIAL LOAD
        # ----------------------------------------------------------------------

        async def refresh_all():
            await load_teams()

        ui.timer(0, refresh_all, once=True)

    apply_layout(content)
