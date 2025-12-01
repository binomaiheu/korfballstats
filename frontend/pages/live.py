import logging

from nicegui import ui
from frontend.api import api_get, api_post
from frontend.layout import apply_layout

from typing import Dict, List, Optional

logger = logging.getLogger('uvicorn.error')


class LiveState:
    """
    Represents the state of the live match.
    """

    def __init__(self):
        self.players: List = []

        # Current Selections
        self.selected_team_id: Optional[int] = None
        self.selected_match: Optional[Dict] = None
        self.selected_player_id: Optional[int] = None

        # Game Data
        self.actions: List = []
        self.active_player_ids: set = set()

        # Clock State
        self.clock_running: bool = False
        self.clock_seconds: int = 0
        self.period: int = 1
        self.timer = None

    @property
    def formatted_time(self):
        mins, secs = divmod(self.clock_seconds, 60)
        return f"{mins:02d}:{secs:02d}"


state = LiveState()


@ui.page('/live')
def live_page():

    def content():

        # ---------------------------------------------------------------
        # HELPERS
        # ---------------------------------------------------------------

        async def load_teams():
            teams = await api_get("/teams")
            team_select.set_options({t["id"]: t["name"] for t in teams})

            # keep selected team if possible
            if state.selected_team_id in [t["id"] for t in teams]:
                team_select.value = state.selected_team_id

        async def load_matches(team_id=None):
            """
            Load matches. If team_id is given: filter only that team’s matches.
            """
            if team_id:
                matches = await api_get(f"/teams/{team_id}/matches")
            else:
                matches = await api_get("/matches")

            match_select.set_options({
                m["id"]: f'{m.get("date", "")[:10]} — {m.get("opponent_name", "")} ({m["team"]["name"]})'
                for m in matches
            })

            # reset selection
            match_select.value = None

        async def load_team_players(team_id: int):
            try:
                return await api_get(f"/teams/{team_id}/players")
            except Exception:
                return []

        # ---------------------------------------------------------------
        # UI UPDATE HANDLERS
        # ---------------------------------------------------------------

        async def on_team_change(team_id):
            state.selected_team_id = team_id

            # Load matches for this team
            await load_matches(team_id)

            # Load players for this team
            players = await load_team_players(team_id)
            state.players = players

            players_column.clear()

            with players_column:
                ui.markdown("### Players for team").classes("mt-4")

                for p in players:
                    player_id = p["id"]
                    player_name = f"{p.get('first_name', 'Unknown')} {p.get('last_name', '')}"
                    active = player_id in state.active_player_ids
                    selected = (state.selected_player_id == player_id)

                    # Determine initial button color
                    def button_class(active, selected):
                        if selected:
                            return "bg-red-500 text-white"
                        if active:
                            return "bg-green-500 text-white"
                        return "bg-gray-300 text-gray-600"

                    with ui.row().classes("items-center gap-4"):

                        # Create button
                        btn = ui.button(
                            f"{player_name}",
                            on_click=lambda _, pid=player_id: on_player_button_click(pid),
                        ).classes(button_class(active, selected))

                        if not active:
                            btn.disable()

                        # Switch handler
                        async def switch_handler(e, pid=player_id, button=btn):
                            is_active = bool(e.value)

                            if is_active:
                                state.active_player_ids.add(pid)
                                button.enable()
                            else:
                                state.active_player_ids.discard(pid)
                                button.disable()

                            # Update button color
                            button.classes(remove="bg-green-500 bg-gray-300 bg-gray-600 bg-red-500 text-white text-gray-600")
                            button.classes(add=button_class(is_active, state.selected_player_id == pid))

                        ui.switch(value=active, on_change=switch_handler)

        # simple handler for clicking a player button (when enabled)
        def on_player_button_click(player_id):
            # If inactive → ignore click
            if player_id not in state.active_player_ids:
                return

            previous = state.selected_player_id
            state.selected_player_id = player_id

            # Notify
            ui.notify(f"Selected player {player_id}")

            # Re-render buttons (lightweight refresh)
            players_column.clear()

            with players_column:
                ui.markdown("### Players for team").classes("mt-4")

                for p in state.players:
                    pid = p["id"]
                    active = pid in state.active_player_ids
                    selected = (state.selected_player_id == pid)

                    def button_class(active, selected):
                        if selected:
                            return "bg-red-500 text-white"
                        if active:
                            return "bg-green-500 text-white"
                        return "bg-gray-300 text-gray-600"

                    with ui.row().classes("items-center gap-4"):
                        btn = ui.button(
                            f"{p.get('first_name','Unknown')} {p.get('last_name','')}",
                            on_click=lambda _, pid=pid: on_player_button_click(pid),
                        ).classes(button_class(active, selected))

                        if not active:
                            btn.disable()

                        ui.switch(
                            value=active,
                            on_change=lambda e, pid=pid, button=btn: None,  # keep your switch logic if needed
                        )



        async def on_match_change(match_id):
            state.selected_match = {"id": match_id}

            # Load players
            players = await load_team_players(state.selected_team_id)
            state.players = players


        # ---------------------------------------------------------------
        # UI LAYOUT
        # ---------------------------------------------------------------

        ui.markdown("### 🏷️ Match Actions")

        with ui.row().classes("items-center gap-4"):
            team_select = ui.select(
                {},
                label="Select team",
                with_input=False,
                on_change=lambda e: on_team_change(e.value),
            )

            match_select = ui.select(
                {},
                label="Select match",
                with_input=False,
                on_change=lambda e: on_match_change(e.value),
            )

        with ui.row().classes("mt-6 gap-8"):
            # container where team players will appear
            players_column = ui.column()

        # ---------------------------------------------------------------
        # INITIAL LOAD
        # ---------------------------------------------------------------
        async def refresh_all():
            await load_teams()

        ui.timer(0, refresh_all, once=True)

    apply_layout(content)
