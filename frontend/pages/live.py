from asyncio import events
import logging

from nicegui import app, ui, events

from backend.schema import ActionType
from frontend.api import api_get, api_post, api_put
from frontend.layout import apply_layout

from typing import Dict, List, Optional

logger = logging.getLogger('uvicorn.error')



class PlayerButton(ui.button):
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
                self.props(f'color="grey-4"')
                self.disable()
            else:
                self.enable()
                if self._selected:
                    self.props(f'color="red"')
                else:
                    self.props(f'color="green"')
        super().update()



class ActionButton(ui.button):
    def __init__(self, action: ActionType, selected: bool, on_click, *args, **kwargs):
        self._action = action
        self._selected = selected
        self._on_click = on_click
        super().__init__(action.name.replace("_", " ").title())
        self.on('click', self.toggle)

        self.update()

    def toggle(self):
        self._selected = not self._selected
        self._on_click(self._action)

    def update(self):
        with self.props.suspend_updates():
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
        self.selected_match_id: Optional[int] = None
        self.selected_match_data: Optional[Dict] = None  # Full match data including is_finalized
        self.selected_player_id: Optional[int] = None
        self.locked_match_id: Optional[int] = None

        # Game Data
        self.actions: List = []
        self.active_player_ids: set = set()

        # Clock State
        self.clock_running: bool = False
        self.clock_seconds: int = 0
        self.period: int = 1
        self.timer = None

        self.player_seconds: dict[int, int] = {}  # Current session playtime
        self.saved_player_seconds: dict[int, int] = {}  # Saved playtime from database

        self.current_action = None
        self.x: float = None
        self.y: float = None
        
        # Auto-save timer
        self.playtime_save_timer = None
        self.clock_display = None

    @property
    def formatted_time(self):
        mins, secs = divmod(self.clock_seconds, 60)
        return f"{mins:02d}:{secs:02d}"
    
    def formatted_player_time(self, player_id):
        # Show total time (saved + current session)
        saved_secs = self.saved_player_seconds.get(player_id, 0)
        current_secs = self.player_seconds.get(player_id, 0)
        total_secs = saved_secs + current_secs
        m, s = divmod(total_secs, 60)
        return f'{m:02d}:{s:02d}'
    
    @property
    def is_match_finalized(self):
        return self.selected_match_data and self.selected_match_data.get("is_finalized", False)

def get_state() -> LiveState:
    client = ui.context.client
    if not hasattr(client, "live_state"):
        client.live_state = LiveState()
    return client.live_state


@ui.page('/live')
def live_page():

    def content():
        state = get_state()

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
        
        async def load_match_data(match_id: int):
            """Load full match data including finalized status"""
            try:
                match_data = await api_get(f"/matches/{match_id}")
                state.selected_match_data = match_data
                return match_data
            except Exception as e:
                logger.error(f"Failed to load match data: {e}")
                return None
        
        async def load_playtime_data(match_id: int):
            """Load saved playtime data from database"""
            try:
                playtime_data = await api_get(f"/playtime/{match_id}")
                # Update saved playtimes
                state.saved_player_seconds = {
                    pp["player_id"]: pp["time_played"]
                    for pp in playtime_data.get("player_playtimes", [])
                }
                # Update clock with saved match time
                state.clock_seconds = playtime_data.get("match_time_registered_s", 0)
                logger.info(f"Loaded playtime data: {state.saved_player_seconds}")
                return playtime_data
            except Exception as e:
                logger.error(f"Failed to load playtime data: {e}")
                # Initialize empty if no playtime data exists
                state.saved_player_seconds = {}
                return None
        
        async def save_playtime_data():
            """Save current playtime data to database"""
            if not state.selected_match_id or state.is_match_finalized:
                return
            
            try:
                # Combine saved and current session times
                total_player_times = {}
                for player_id in set(list(state.saved_player_seconds.keys()) + list(state.player_seconds.keys())):
                    saved = state.saved_player_seconds.get(player_id, 0)
                    current = state.player_seconds.get(player_id, 0)
                    total_player_times[player_id] = saved + current
                
                time_update = {
                    "match_time_registered_s": state.clock_seconds,
                    "player_time_registered_s": total_player_times
                }
                
                await api_put(f"/playtime/{state.selected_match_id}", time_update)
                logger.info(f"Saved playtime data: {time_update}")
                
                # Update saved times to include current session
                state.saved_player_seconds = total_player_times
                # Reset current session times
                state.player_seconds = {}
                
            except Exception as e:
                logger.error(f"Failed to save playtime data: {e}")

        async def lock_match(match_id: int) -> bool:
            try:
                await api_post(f"/matches/{match_id}/lock", {})
                state.locked_match_id = match_id
                app.storage.user["locked_match_id"] = match_id
                return True
            except Exception as e:
                detail = str(e)
                if e.args and isinstance(e.args[0], dict):
                    detail = e.args[0].get("detail", detail)
                ui.notify(f"Match is locked: {detail}", type="warning")
                return False

        async def unlock_match(match_id: int) -> None:
            try:
                await api_post(f"/matches/{match_id}/unlock", {})
            except Exception:
                return
            app.storage.user.pop("locked_match_id", None)
        
        async def finalize_match():
            """Finalize the current match"""
            if not state.selected_match_id:
                return
            
            # Save playtime before finalizing
            await save_playtime_data()
            
            try:
                # Finalize endpoint doesn't need a body, but api_post expects json
                match_data = await api_post(f"/matches/{state.selected_match_id}/finalize", {})
                state.selected_match_data = match_data
                logger.info(f"Match {state.selected_match_id} finalized")
                if state.locked_match_id:
                    await unlock_match(state.locked_match_id)
                    state.locked_match_id = None
                
                # Refresh UI to show finalized state
                clock_area.refresh()
                finalize_button_area.refresh()
                render_actions()
                render_players(state.players)
                
                ui.notify("Match finalized successfully", type="positive")
            except Exception as e:
                logger.error(f"Failed to finalize match: {e}")
                ui.notify(f"Failed to finalize match: {str(e)}", type="negative")


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
            if state.is_match_finalized:
                ui.notify("Cannot modify clock for a finalized match", type="warning")
                return
            state.clock_running = not state.clock_running
            clock_area.refresh()

        def tick():
            if state.clock_running:
                state.clock_seconds += 1
                # Update the visual clock
                if state.clock_display:
                    state.clock_display.text = state.formatted_time

                # per-player clocks
                for pid in state.active_player_ids:
                    state.player_seconds[pid] = state.player_seconds.get(pid, 0) + 1
                
                # Update player playtime display (only if players are loaded)
                if state.players:
                    render_players(state.players)


        def reset_clock():
            if state.is_match_finalized:
                ui.notify("Cannot reset clock for a finalized match", type="warning")
                return
            state.clock_running = False
            state.clock_seconds = 0
            clock_area.refresh()

        def set_clock_dialog():
            if state.is_match_finalized:
                ui.notify("Cannot set time for a finalized match", type="warning")
                return
            set_time_number.value = state.clock_seconds
            set_time_dialog.open()
        
        # create the timer
        state.timer = ui.timer(1.0, tick)


        # ---------------------------------------------------------------
        # UI UPDATE HANDLERS
        # ---------------------------------------------------------------
        async def submit(result: bool):
            if not state.selected_match_id or not state.selected_player_id or not state.current_action:
                logger.warning("Cannot submit action: missing selection")
                return
            
            if state.is_match_finalized:
                ui.notify("Cannot add actions to a finalized match", type="warning")
                return

            action_data = {
                "match_id": state.selected_match_id,
                "player_id": state.selected_player_id,
                "timestamp": state.clock_seconds,
                "x": state.x,
                "y": state.y,
                "period": state.period,
                "action": state.current_action,
                "result": result
            }

            try:
                await api_post("/actions", action_data)
                logger.info(f"Submitted action: {action_data}")
            except Exception as e:
                logger.error(f"Failed to submit action: {e}")
                ui.notify(f"Failed to submit action: {str(e)}", type="negative")

            # Optionally, you could reset the state or provide feedback to the user here
            state.current_action = None
            state.selected_player_id = None
            state.x = None
            state.y = None

            # update gui
            render_actions()
            render_players(state.players)
            ii.content = ""  # Clear the playfield indicator


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
            if state.locked_match_id:
                await unlock_match(state.locked_match_id)
                state.locked_match_id = None
            finalize_button_area.refresh()


        async def on_match_change(match_id):
            # Save playtime for previous match if exists
            if state.selected_match_id and not state.is_match_finalized:
                await save_playtime_data()

            if state.locked_match_id:
                await unlock_match(state.locked_match_id)
                state.locked_match_id = None
            
            state.selected_match_id = match_id
            state.selected_match_data = None
            players_column.clear()

            logger.info(f"Switching match to {match_id}")
            if match_id is None:
                # Reset state
                state.saved_player_seconds = {}
                state.player_seconds = {}
                state.clock_seconds = 0
                clock_area.refresh()
                finalize_button_area.refresh()
                return

            if not await lock_match(match_id):
                match_select.value = None
                state.selected_match_id = None
                return
            
            # Load match data (including finalized status)
            await load_match_data(match_id)
            finalize_button_area.refresh()
            
            # Load playtime data
            await load_playtime_data(match_id)
            
            # Load players
            state.players = await load_team_players(state.selected_team_id)
            state.active_player_ids = set()  # Reset active players
            state.player_seconds = {}  # Reset current session times

            render_actions()
            render_players(state.players)
            clock_area.refresh()
            finalize_button_area.refresh()
            
            # Start auto-save timer (save every 30 seconds)
            if state.playtime_save_timer:
                state.playtime_save_timer.deactivate()
            state.playtime_save_timer = ui.timer(30.0, lambda: save_playtime_data(), active=True)

        async def handle_disconnect():
            if state.locked_match_id:
                await unlock_match(state.locked_match_id)
                state.locked_match_id = None


        def on_action_button_click(action_type):
            if state.current_action == action_type:
                # Deselect
                state.current_action = None
                logger.info(f"Deselected action {action_type}")
            else:
                # Select new action
                state.current_action = action_type
                logger.info(f"Selected action {action_type}")

            # Re-render actions (lightweight refresh)
            render_actions()



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
            if state.is_match_finalized:
                ui.notify("Cannot modify active players for a finalized match", type="warning")
                # Reset switch to previous state
                e.value = not e.value
                return
            
            is_active = bool(e.value)
            button._active = is_active

            if is_active:
                state.active_player_ids.add(pid)
            else:
                state.active_player_ids.discard(pid)
            
            button.update()
            render_players(state.players)


        def render_actions():
            action_column.clear()

            with action_column:
                for action_type in ActionType:
                    act_btn = ActionButton(
                        action_type,
                        action_type == state.current_action,
                        on_click=on_action_button_click
                    )
                    if state.is_match_finalized:
                        act_btn.disable()


        def render_players(players):
            players_column.clear()
 
            with players_column:
                with ui.grid(columns=2).classes("gap-4"):
                    sorted_players = sorted(
                        players,
                        key=lambda p: (
                            p["id"] not in state.active_player_ids,
                            p.get("last_name", ""),
                            p.get("first_name", ""),
                        ),
                    )
                    for p in sorted_players:
                        player_id = p["id"]
                        player_name = f"{p.get('first_name', 'Unknown')} ({p.get('number', '')})"
                        is_active = player_id in state.active_player_ids
                        is_selected = (state.selected_player_id == player_id)

                        # Create button
                        with ui.grid().classes("grid-cols-[auto_3rem_4rem] items-center gap-2"):

                            # Create the ToggleButton
                            btn = PlayerButton(
                                player_id=player_id,
                                player_name=player_name,
                                active=is_active,
                                selected=is_selected,
                                on_click=on_player_button_click,
                            )#.classes("w-32 items-start")
                            
                            # Use lambda with default arguments to freeze the values of player_id and btn
                            player_switch = ui.switch(value=is_active, on_change=lambda e, pid=player_id, button=btn: on_switch_handler(e, pid, button))
                            if state.is_match_finalized:
                                player_switch.disable()

                            # playtime (shows total: saved + current session)
                            ui.label(state.formatted_player_time(player_id)).classes("text-xs text-grey-6")

        # ---------------------------------------------------------
        # UI COMPONENTS (REFRESHABLE)
        # ---------------------------------------------------------
        @ui.refreshable
        def clock_area():
            if not state.selected_match_id:
                ui.label("No match selected").classes("text-xs font-bold text-grey-6")
                return

            with ui.card().classes('w-full items-center bg-grey-2'):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("GAME CLOCK").classes("text-xs font-bold text-grey-6")
                    if state.is_match_finalized:
                        ui.badge("FINALIZED", color="red").classes("text-xs")
                
                with ui.row().classes("items-center"):
                    # Period Controls
                    period_minus = ui.button("-", on_click=lambda: setattr(state, 'period', max(1, state.period - 1)) or clock_area.refresh()).props("round sm")
                    ui.label(f"P{state.period}").classes("text-xl font-bold mx-2")
                    period_plus = ui.button("+", on_click=lambda: setattr(state, 'period', state.period + 1) or clock_area.refresh()).props("round sm")
                    
                    if state.is_match_finalized:
                        period_minus.disable()
                        period_plus.disable()
                    
                    ui.separator().props("vertical").classes("mx-4")
                    
                    # Time Display
                    state.clock_display = ui.label(state.formatted_time).classes("text-4xl font-mono font-bold mx-4 bg-black text-red-500 px-2 rounded")
                    
                    ui.separator().props("vertical").classes("mx-4")

                    # Controls
                    clock_button = None
                    if state.clock_running:
                        clock_button = ui.button("PAUSE", on_click=toggle_clock, color="warning", icon="pause")
                    else:
                        clock_button = ui.button("START", on_click=toggle_clock, color="positive", icon="play_arrow")
                    
                    if state.is_match_finalized:
                        clock_button.disable()

        @ui.refreshable
        def finalize_button_area():
            if state.selected_match_id and not state.is_match_finalized:
                ui.button(
                    "Finalize Match",
                    on_click=finalize_match,
                    color="red",
                    icon="lock",
                ).classes("ml-2")
                    

        def mouse_handler(e: events.MouseEventArguments):
            color = 'Red' 
#            ii.content += f'<circle cx="{e.image_x}" cy="{e.image_y}" r="5" fill="none" stroke="{color}" stroke-width="2" />'
            ii.content = f'<circle cx="{e.image_x}" cy="{e.image_y}" r="4" fill="none" stroke="{color}" stroke-width="3" />'
            #state.x = (e.image_x-50)/700*40
            #state.y = (e.image_y-50)/300*20
            state.x = e.image_x
            state.y = e.image_y

            print(f'{e.type} at ({state.x:.1f}, {state.y:.1f})')


        # ---------------------------------------------------------------
        # UI LAYOUT
        # ---------------------------------------------------------------
        ui.context.client.on_disconnect(handle_disconnect)
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
   
            with ui.button(icon="settings", color="grey").props("flat round") as settings_btn:
                with ui.menu():
                    ui.menu_item("Set Time", on_click=set_clock_dialog)
                    ui.menu_item("Reset", on_click=reset_clock)
                    ui.separator()
                    ui.menu_item("Save Playtime", on_click=lambda: save_playtime_data())
                    finalize_item = ui.menu_item(
                        "Finalize Match" if not state.is_match_finalized else "Match Finalized",
                        on_click=lambda: finalize_match() if (state.selected_match_id and not state.is_match_finalized) else None,
                    )
                    if not state.selected_match_id or state.is_match_finalized:
                        finalize_item.disable()
            
            finalize_button_area()


        with ui.row():
            clock_area()

        with ui.row().classes("items-start gap-4"):
            with ui.card():
                ui.label("Actions").classes("text-xs font-bold text-grey-6")
                action_column = ui.row().classes("items-center gap-2 flex-wrap")
            with ui.card():
                ui.label("Result").classes("text-xs font-bold text-grey-6")
                with ui.row().classes("items-center gap-2"):
                    ok_button = ui.button(
                        "Ok / Score",
                        on_click=lambda x: submit(True),
                        icon="thumb_up"
                    )
                    if state.is_match_finalized:
                        ok_button.disable()
                    miss_button = ui.button(
                        "Gemist",
                        on_click=lambda x: submit(False),
                        icon="thumb_down"
                    )
                    if state.is_match_finalized:
                        miss_button.disable()

        with ui.row().classes("items-start gap-4"):
            src = 'korfball_field.svg'
            #src = 'korfball.svg'
            #ii = ui.interactive_image(src, on_mouse=mouse_handler, events=['mousedown', 'mouseup'], cross=True)
            with ui.card():
                ui.label("Playfield").classes("text-xs font-bold text-grey-6")
                ii = ui.interactive_image(src, on_mouse=mouse_handler, events=['mousedown']).style('width: 600px; height: auto')
            with ui.card():
                ui.label("Players").classes("text-xs font-bold text-grey-6")
                players_column = ui.column()



        # ---------------------------------------------------------------
        # INITIAL LOAD
        # ---------------------------------------------------------------
        async def refresh_all():
            await load_teams()

        ui.timer(0, refresh_all, once=True)

    apply_layout(content)
