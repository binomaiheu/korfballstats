import logging

from nicegui import ui
from frontend.api import api_get, api_post
from frontend.layout import apply_layout

logger = logging.getLogger('uvicorn.error')

EVENT_TYPES = [
    ("goal", "Goal"),
    ("goal_free_throw", "Free Throw"),
    ("goal_inside", "Inside"),
    ("shot", "Shot"),
    ("foul", "Foul"),
    ("penalty", "Penalty"),
]

@ui.page('/live')
def live_page():

    def content():

        # ---------------------------
        # STATE
        # ---------------------------
        state = {
            "matches": [],
            "teams": {},
            "events": [],
            "players": [],
            "selected_match": None,
            "selected_team_id": None,
            "selected_player_id": None,
        }

        # ---------------------------
        # LOAD HELPERS
        # ---------------------------

        async def load_matches():
            state["matches"] = await api_get("/matches")
            match_select.set_options({
                m["id"]: f'{m.get("date", "")[:10]} — {m.get("opponent_name", "")} (Team {m["team_id"]})'
                for m in state["matches"]
            })

        async def load_teams():
            teams = await api_get("/teams")
            state["teams"] = {t["id"]: t for t in teams}
            team_select.set_options({t["id"]: t["name"] for t in teams})

            # keep selected team if possible
            if state["selected_team_id"] in state["teams"]:
                team_select.value = state["selected_team_id"]

        async def load_events():
            try:
                state["events"] = await api_get("/events")
            except Exception:
                state["events"] = []

        async def load_team_players(team_id: int):
            """Your backend must expose /teams/<id>/players"""
            try:
                return await api_get(f"/teams/{team_id}/players")
            except Exception:
                return []

        # ---------------------------
        # UI HELPERS
        # ---------------------------

        def render_player_buttons():
            players_grid.clear()
            with players_grid:
                for p in state["players"]:
                    pid = p["id"]
                    classes = "q-pa-xs"
                    if pid == state["selected_player_id"]:
                        classes += " bg-red text-white"   # <-- make selected player red
                    else:
                        classes += " bg-grey-3 text-black"          # optional: light background for others

                    ui.button(
                        p["name"],
                        on_click=lambda e, pid=pid: select_player(pid),
                    ).classes(classes)

        def select_player(pid: int):
            state["selected_player_id"] = pid
            render_player_buttons()

        # ---------------------------
        # STATS AGGREGATION
        # ---------------------------

        def aggregate_stats(match_id: int, team_id: int):
            players = state["players"]
            et_keys = [key for key, _ in EVENT_TYPES]

            totals = {
                p["id"]: {
                    **{k: 0 for k in et_keys},
                    "player_name": p["name"],
                }
                for p in players
            }

            for e in state["events"]:
                try:
                    if int(e.get("match_id")) != match_id:
                        continue
                    if int(e.get("team_id")) != team_id:
                        continue
                except Exception:
                    continue

                pid = e.get("player_id")
                et = e.get("type")
                val = int(e.get("value", 0))

                if pid in totals and et in totals[pid]:
                    totals[pid][et] += val

            rows = []
            for pid, d in totals.items():
                row = {"player_name": d["player_name"], "player_id": pid}
                for et in et_keys:
                    row[et] = d[et]
                rows.append(row)
            return rows

        # ---------------------------
        # EVENT HANDLERS
        # ---------------------------

        async def on_match_change(match_id: int):
            sel = next((m for m in state["matches"] if m["id"] == match_id), None)
            state["selected_match"] = sel

            if not sel:
                players_grid.clear()
                stats_table.rows = []
                return

            # set team
            state["selected_team_id"] = sel["team_id"]
            team_select.value = sel["team_id"]

            # load players
            state["players"] = await load_team_players(sel["team_id"])
            render_player_buttons()

            # auto-select first player
            if state["players"]:
                state["selected_player_id"] = state["players"][0]["id"]
                render_player_buttons()

            # update stats
            stats_table.rows = aggregate_stats(sel["id"], sel["team_id"])

        async def post_event(event_type: str, value: int):
            if not state["selected_match"] or not state["selected_player_id"]:
                ui.notify("Select a match and a player first", color="warning")
                return

            payload = {
                "match_id": state["selected_match"]["id"],
                "player_id": state["selected_player_id"],
                "team_id": state["selected_team_id"],
                "type": event_type,
                "value": value,
            }

            try:
                print(payload)
                created = await api_post("/events", payload)
                state["events"].append(created)
                stats_table.rows = aggregate_stats(
                    payload["match_id"], payload["team_id"]
                )
            except Exception as e:
                ui.notify(f"Failed to post event: {e}", color="negative")

        async def refresh_all():
            await load_matches()
            await load_teams()
            await load_events()
            if state["selected_match"]:
                await on_match_change(state["selected_match"]["id"])

        # ---------------------------
        # UI LAYOUT
        # ---------------------------

        ui.markdown("## 🏷️ Match Events")

        with ui.row().classes("items-center gap-4"):
            match_select = ui.select(
                [],
                label="Select match",
                with_input=False,
                on_change=lambda e: on_match_change(e.value),
            )
            team_select = ui.select([], label="Team", with_input=False).props("readonly")
            ui.button("Refresh", on_click=refresh_all)

        ui.separator()

        ui.markdown("### 👥 Players")
        players_grid = ui.row().classes("gap-2 wrap")

        ui.separator()

        ui.markdown("### 🎯 Events")
        with ui.row().classes("items-center gap-2"):
            for key, label in EVENT_TYPES:
                ui.button(f"+ {label}", on_click=lambda k=key: post_event(k, 1)).props("size=small")
                ui.button(f"- {label}", on_click=lambda k=key: post_event(k, -1)).props("size=small")

        ui.separator()

        ui.markdown("### 📊 Statistics (per player)")
        cols = [{"name": "player_name", "label": "Player", "field": "player_name"}]
        for key, label in EVENT_TYPES:
            cols.append({"name": key, "label": label, "field": key})

        stats_table = ui.table(columns=cols, rows=[], row_key="player_id").classes("w-full mt-4")

        ui.timer(0, refresh_all, once=True)


    # set layout
    apply_layout(content)