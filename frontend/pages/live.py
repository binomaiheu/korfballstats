import logging

from nicegui import ui
from frontend.api import api_get, api_post
from frontend.layout import apply_layout

from typing import Dict, List, Optional

logger = logging.getLogger('uvicorn.error')



class ToggleButton(ui.button):
    def __init__(self, player_id, player_name, active, selected, on_click, *args, **kwargs):
        self.player_id = player_id
        self._active = active # player is on the field
        self._selected = selected # player is select for inputting
        self._on_click = on_click
        super().__init__(player_name, *args, **kwargs)
        self.on('click', self.toggle)

        # Set the initial state
        self.update()

    def toggle(self) -> None:
        """Handle button click and toggle the state."""
        if not self._active:
            return  # Ignore clicks if the button is disabled
        self._on_click(self.player_id)  # Call the provided click handler

    def update(self) -> None:
        """Update the button's appearance based on its state."""

        with self.props.suspend_updates():
            if not self._active:
                self.props(f'color="blue"')
                self.disable()
            else:
                self.enable()
                if self._selected:
                    self.props(f'color="red"')
                else:
                    self.props(f'color="green"')
        super().update()


class LiveState:
    """
    Represents the state of the live match.
    """

    def __init__(self):
        self.players: List = []

        # Current Selections
        self.selected_team_id: Optional[int] = None
        self.selected_match_id: Optional[Dict] = None
        self.selected_player_id: Optional[int] = None

        # Game Data
        self.actions: List = []
        self.active_player_ids: set = set()

        # Clock State
        self.clock_running: bool = False
        self.clock_seconds: int = 0
        self.period: int = 1
        self.timer = None

        self.player_seconds: dict[int, int] = {}

    @property
    def formatted_time(self):
        mins, secs = divmod(self.clock_seconds, 60)
        return f"{mins:02d}:{secs:02d}"
    
    def formatted_player_time(self, player_id):
        secs = state.player_seconds.get(player_id, 0)
        m, s = divmod(secs, 60)
        return f'{m:02d}:{s:02d}'

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
            Load matches. If team_id is given: filter only that team's matches.
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


        # ---------------------------------------------------------
        # GAME CLOCK LOGIC
        # ---------------------------------------------------------


        # the ui dialog
        with ui.dialog() as set_time_dialog:
            with ui.card():
                ui.label("Set Time (Seconds)")
                set_time_number = ui.number(value=state.clock_seconds)
                
                def save():
                    state.clock_seconds = int(set_time_number.value)
                    clock_area.refresh()
                    set_time_dialog.close()
                
                ui.button("Set", on_click=save)

        def toggle_clock():
            state.clock_running = not state.clock_running
            clock_area.refresh()

        def tick():
            if state.clock_running:
                state.clock_seconds += 1
                # Here we could theoretically update playtime for active_player_ids
                # But we don't have a DB model for it, so we just update the visual clock
                if clock_display:
                    clock_display.text = state.formatted_time

                # per-player clocks
                for pid in state.active_player_ids:
                    state.player_seconds[pid] = state.player_seconds.get(pid, 0) + 1


        def reset_clock():
            state.clock_running = False
            state.clock_seconds = 0
            clock_area.refresh()

        def set_clock_dialog():
            set_time_number.value = state.clock_seconds
            set_time_dialog.open()
        
        # create the timer
        state.timer = ui.timer(1.0, tick)


        # ---------------------------------------------------------------
        # UI UPDATE HANDLERS
        # ---------------------------------------------------------------

        async def on_team_change(team_id):
            state.selected_team_id = team_id

            logger.info(f"Switching team to {team_id}")
            # Load matches for this team
            await load_matches(team_id)

            # Reset selected player & match
            state.selected_match_id = None
            state.selected_player_id = None
            state.active_player_ids.clear()
            state.players = [] # Clear players            

            players_column.clear()


        async def on_match_change(match_id):
            state.selected_match_id = match_id
            players_column.clear()

            logger.info(f"Switching match to {match_id}")
            if match_id is None:
                clock_area.refresh()
                return
            
            # Load players
            state.players = await load_team_players(state.selected_team_id)
            state.active_player_ids = set()  # Reset active players

            render_players(state.players)
            clock_area.refresh()


        # simple handler for clicking a player button (when enabled)
        def on_player_button_click(player_id):
            # If inactive → ignore click
            if player_id not in state.active_player_ids:
                return

            if state.selected_player_id == player_id:
                # Deselect if already selected
                state.selected_player_id = None
                logger.info(f"Deselected player {player_id}")
            else:
                # Select this player
                state.selected_player_id = player_id
                logger.info(f"Selected player {player_id}")


            # Re-render buttons (lightweight refresh)
            render_players(state.players)


        # Switch handler
        async def on_switch_handler(e, pid, button):
            is_active = bool(e.value)
            button._active = is_active

            if is_active:
                state.active_player_ids.add(pid)
            else:
                state.active_player_ids.discard(pid)
            
            button.update() 


        def render_players(players):
            players_column.clear()
 
            for p in players:
                player_id = p["id"]
                player_name = f"{p.get('first_name', 'Unknown')} ({p.get('number', '')})"
                is_active = player_id in state.active_player_ids
                is_selected = (state.selected_player_id == player_id)


                # Create button
                with players_column:
                    with ui.row().classes("items-center gap-4"):

                        # Create the ToggleButton
                        btn = ToggleButton(
                            player_id=player_id,
                            player_name=player_name,
                            active=is_active,
                            selected=is_selected,
                            on_click=on_player_button_click,
                        ).classes("w-32 items-start")
                        
                        # Use lambda with default arguments to freeze the values of player_id and btn
                        ui.switch(value=is_active, on_change=lambda e, pid=player_id, button=btn: on_switch_handler(e, pid, button))

                        # playtime
                        ui.label().bind_text_from(state.player_seconds, player_id, lambda secs: f"{secs // 60:02d}:{secs % 60:02d}").classes("text-xs text-grey-6")
 
        # ---------------------------------------------------------
        # UI COMPONENTS (REFRESHABLE)
        # ---------------------------------------------------------
        @ui.refreshable
        def clock_area():
            if not state.selected_match_id:
                ui.label("No match selected").classes("text-xs font-bold text-grey-6")
                return

            with ui.card().classes('w-full items-center bg-grey-2'):
                ui.label("GAME CLOCK").classes("text-xs font-bold text-grey-6")
                
                with ui.row().classes("items-center"):
                    # Period Controls
                    ui.button("-", on_click=lambda: setattr(state, 'period', max(1, state.period - 1)) or clock_area.refresh()).props("round sm")
                    ui.label(f"P{state.period}").classes("text-xl font-bold mx-2")
                    ui.button("+", on_click=lambda: setattr(state, 'period', state.period + 1) or clock_area.refresh()).props("round sm")
                    
                    ui.separator().props("vertical").classes("mx-4")
                    
                    # Time Display
                    global clock_display
                    clock_display = ui.label(state.formatted_time).classes("text-4xl font-mono font-bold mx-4 bg-black text-red-500 px-2 rounded")
                    
                    ui.separator().props("vertical").classes("mx-4")

                    # Controls
                    if state.clock_running:
                        ui.button("PAUSE", on_click=toggle_clock, color="warning", icon="pause")
                    else:
                        ui.button("START", on_click=toggle_clock, color="positive", icon="play_arrow")
                    

          

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
            ).classes("w-32")  # Make the select wider

            match_select = ui.select(
                {},
                label="Select match",
                with_input=False,
                on_change=lambda e: on_match_change(e.value),
            ).classes("w-48")  # Make the select wider
   
            with ui.button(icon="settings", color="grey").props("flat round"):
                with ui.menu():
                    ui.menu_item("Set Time", on_click=set_clock_dialog)
                    ui.menu_item("Reset", on_click=reset_clock) 


        with ui.row():
            clock_area()

        with ui.row():
            with ui.card():
                ui.label("Players").classes("text-xs font-bold text-grey-6")
                players_column = ui.column()
            with ui.card():
                ui.label("Actions").classes("text-xs font-bold text-grey-6")
                action_column = ui.column()

        # ---------------------------------------------------------------
        # INITIAL LOAD
        # ---------------------------------------------------------------
        async def refresh_all():
            await load_teams()

        ui.timer(0, refresh_all, once=True)

    apply_layout(content)
