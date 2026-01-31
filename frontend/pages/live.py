import asyncio
from asyncio import events
import difflib
import logging

from nicegui import app, ui, events

from backend.schema import ActionType
from frontend.api import api_post
from frontend.layout import apply_layout
from frontend.pages.live_controller import get_live_controller
from backend.services.action_events import subscribe as subscribe_actions, unsubscribe as unsubscribe_actions
from backend.services.join_events import subscribe as subscribe_joins, unsubscribe as unsubscribe_joins
from backend.services.join_decision_events import subscribe as subscribe_join_decisions, unsubscribe as unsubscribe_join_decisions
from backend.services.clock_events import subscribe as subscribe_clock, unsubscribe as unsubscribe_clock, notify as notify_clock
from backend.services.active_players_events import subscribe as subscribe_active_players, unsubscribe as unsubscribe_active_players, notify as notify_active_players

from typing import List

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



ACTION_LABELS = {
    ActionType.SHOT: "Schot",
    ActionType.KORTE_KANS: "Korte kans",
    ActionType.VRIJWORP: "Vrijworp",
    ActionType.STRAFWORP: "Strafworp",
    ActionType.INLOPER: "Inloper",
    ActionType.REBOUND: "Rebound",
    ActionType.ASSIST: "Assist",
    ActionType.STEAL: "Steal",
}


def format_action_label(action_value: str | ActionType) -> str:
    if isinstance(action_value, ActionType):
        return ACTION_LABELS.get(action_value, action_value.name.replace("_", " ").title())
    for action_type in ActionType:
        if action_type.value == action_value or action_type.name == action_value:
            return ACTION_LABELS.get(action_type, action_type.name.replace("_", " ").title())
    return str(action_value or "").replace("_", " ").title()


class ActionButton(ui.button):
    def __init__(self, action: ActionType, selected: bool, on_click, *args, **kwargs):
        self._action = action
        self._selected = selected
        self._on_click = on_click
        super().__init__(format_action_label(action))
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


@ui.page('/live')
def live_page():

    def content():
        controller = get_live_controller()
        state = controller.state
        state.api_token = app.storage.user.get("token")
        state.user_id = app.storage.user.get("user_id")
        state.username = app.storage.user.get("username")

        # ---------------------------------------------------------------
        # HELPERS
        # ---------------------------------------------------------------
        LIVE_STATE_KEY = "live_state"

        async def load_teams():
            teams = await controller.load_teams(token=state.api_token)
            team_select.set_options({t["id"]: t["name"] for t in teams})

            # keep selected team if possible
            if state.selected_team_id in [t["id"] for t in teams]:
                team_select.value = state.selected_team_id

        async def load_matches(team_id=None):
            """
            Load matches. If team_id is given: filter only that team's matches.
            """
            matches = await controller.load_matches(team_id, token=state.api_token)

            match_select.set_options({
                m["id"]: f'{m.get("date", "")[:10]} — {m.get("opponent_name", "")} ({m["team"]["name"]})'
                for m in matches
            })

            # reset selection
            match_select.value = None

        async def load_team_players(team_id: int):
            return await controller.load_team_players(team_id, token=state.api_token)
        
        async def load_match_data(match_id: int):
            """Load full match data including finalized status"""
            return await controller.load_match_data(match_id, token=state.api_token)
        
        async def load_playtime_data(match_id: int):
            """Load saved playtime data from database"""
            return await controller.load_playtime_data(match_id, token=state.api_token)
        
        async def save_playtime_data():
            """Save current playtime data to database"""
            await controller.save_playtime_data(token=state.api_token)

        async def handle_voice_command(command: str) -> None:
            if not state.selected_match_id:
                return
            if not can_edit_match():
                ui.notify("Match is locked by another user", type="warning")
                return

            text = command.strip().lower()
            if not text:
                return

            def normalize(text_value: str) -> str:
                cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text_value.lower())
                return " ".join(cleaned.split())

            text = normalize(text)

            async def confirm_voice_choice(message: str) -> bool:
                done = asyncio.Event()
                result = {"value": False}
                with ui.dialog() as dialog, ui.card():
                    ui.label(message).classes("text-sm")
                    with ui.row().classes("gap-2 mt-2"):
                        ui.button("OK", on_click=lambda: (result.update(value=True), dialog.close(), done.set()))
                        ui.button("Cancel", on_click=lambda: (dialog.close(), done.set()))
                dialog.open()
                await done.wait()
                return result["value"]

            # Strict order: action -> player -> result
            tokens = text.split()
            if len(tokens) < 2:
                ui.notify("Voice format: actie speler resultaat", type="warning")
                return
            result_words = {"ok", "oke", "score", "raak", "doelpunt", "goal", "gemist", "mis", "naast"}
            result_index = None
            for idx, token in enumerate(tokens):
                if token in result_words:
                    result_index = idx
                    break
            special_no_result = {ActionType.REBOUND, ActionType.ASSIST, ActionType.STEAL}
            if result_index is None:
                action_words = tokens[0]
                player_words = " ".join(tokens[1:]).strip()
                result_word = None
            else:
                if result_index == 0:
                    ui.notify("Say result last: ok/score or gemist/mis", type="warning")
                    return
                action_words = " ".join(tokens[:max(1, result_index - 1)]).strip()
                player_words = " ".join(tokens[max(1, result_index - 1):result_index]).strip()
                result_word = tokens[result_index]

            # Select action
            action_phrases = {
                "schot": ActionType.SHOT,
                "korte kans": ActionType.KORTE_KANS,
                "kortekans": ActionType.KORTE_KANS,
                "vrijworp": ActionType.VRIJWORP,
                "strafworp": ActionType.STRAFWORP,
                "penalty": ActionType.STRAFWORP,
                "inloper": ActionType.INLOPER,
                "rebound": ActionType.REBOUND,
                "assist": ActionType.ASSIST,
                "steun": ActionType.ASSIST,
                "steal": ActionType.STEAL,
                "stelen": ActionType.STEAL,
            }
            def best_match(value: str, candidates: list[str]) -> tuple[str | None, float]:
                best_score = 0.0
                best_value = None
                for candidate in candidates:
                    score = difflib.SequenceMatcher(None, value, candidate).ratio()
                    if score > best_score:
                        best_score = score
                        best_value = candidate
                return best_value, best_score

            action_value, action_score = best_match(action_words, list(action_phrases.keys()))
            if not action_value or action_score < 0.65:
                ui.notify("Action not recognized", type="warning")
                return
            if action_score < 0.8:
                if not await confirm_voice_choice(f'Action "{action_value}"?'):
                    return
            on_action_button_click(action_phrases[action_value])
            action_type = action_phrases[action_value]
            if result_word is None and action_type not in special_no_result:
                ui.notify("Say result last: ok/score or gemist/mis", type="warning")
                return

            matched_player_label = None

            # Select player by number
            player_tokens = [t for t in player_words.split() if t not in {"speler", "nummer"}]
            for token in player_tokens:
                if token.isdigit():
                    number = int(token)
                    for player in state.players:
                        if player.get("number") == number:
                            on_player_button_click(player["id"])
                            player_words = ""
                            matched_player_label = f"#{number}"
                            break

            # Select player by fuzzy name match
            candidates = []
            candidate_map = {}
            for player in state.players:
                first = (player.get("first_name") or "").lower().strip()
                last = (player.get("last_name") or "").lower().strip()
                full = f"{first} {last}".strip()
                for name in [first, last, full]:
                    if not name:
                        continue
                    candidates.append(name)
                    candidate_map[name] = player["id"]

            if player_words:
                best_player, player_score = best_match(player_words, candidates)
                if not best_player or player_score < 0.65:
                    ui.notify("Player not recognized", type="warning")
                    return
                if player_score < 0.85:
                    if not await confirm_voice_choice(f'Player "{best_player}"?'):
                        return
                on_player_button_click(candidate_map[best_player])
                matched_player_label = best_player

            # Submit result
            player_label = matched_player_label or player_words or "speler"
            action_label = format_action_label(action_type)
            if action_type in special_no_result:
                await submit(True)
                ui.notify(f"Voice: {action_label} → {player_label}", type="positive")
            elif result_word in {"ok", "oke", "score", "raak", "doelpunt", "goal"}:
                await submit(True)
                ui.notify(f"Voice: {action_label} → {player_label} (score)", type="positive")
            elif result_word in {"gemist", "mis", "naast"}:
                await submit(False)
                ui.notify(f"Voice: {action_label} → {player_label} (miss)", type="warning")

        async def poll_voice_queue():
            if not getattr(state, "voice_enabled", False):
                return
            text = await ui.run_javascript(
                "return (window.__voice_queue && window.__voice_queue.shift()) || null"
            )
            if text:
                await handle_voice_command(str(text))

        def persist_live_state() -> None:
            action_value = None
            if state.current_action is not None:
                action_value = state.current_action.value if hasattr(state.current_action, "value") else state.current_action
            app.storage.user[LIVE_STATE_KEY] = {
                "selected_team_id": state.selected_team_id,
                "selected_match_id": state.selected_match_id,
                "active_player_ids": sorted(state.active_player_ids),
                "current_action": action_value,
                "period": state.period,
                "period_minutes": state.period_minutes,
                "total_periods": state.total_periods,
            }

        async def restore_live_state() -> None:
            data = app.storage.user.get(LIVE_STATE_KEY) or {}
            team_id = data.get("selected_team_id")
            match_id = data.get("selected_match_id")
            action_value = data.get("current_action")
            active_ids = set(data.get("active_player_ids") or [])

            if team_id:
                state.selected_team_id = team_id
                team_select.value = team_id
                await load_matches(team_id)

            if match_id:
                match_select.value = match_id
                await on_match_change(match_id)

                if active_ids:
                    state.active_player_ids = active_ids
                    render_players(state.players)

                if action_value:
                    try:
                        state.current_action = ActionType(action_value)
                    except Exception:
                        state.current_action = None
                    render_actions()

        async def lock_match(match_id: int) -> bool:
            success, detail = await controller.lock_match(match_id, token=state.api_token)
            if not success and detail != "locked":
                ui.notify(f"Match is locked: {detail}", type="warning")
            state.is_collaborator = detail == "collaborator"
            if success and state.selected_match_data:
                state.selected_match_data["locked_by_user_id"] = state.user_id
            return success

        def build_clock_payload() -> dict:
            return {
                "clock_running": state.clock_running,
                "clock_seconds": state.clock_seconds,
                "remaining_seconds": state.remaining_seconds,
                "period": state.period,
                "period_minutes": state.period_minutes,
                "total_periods": state.total_periods,
                "is_finalized": state.is_match_finalized,
                "locked_by_user_id": state.selected_match_data.get("locked_by_user_id") if state.selected_match_data else None,
            }

        def broadcast_clock_state() -> None:
            if not state.selected_match_id:
                return
            if not state.selected_match_data:
                return
            if state.selected_match_data.get("locked_by_user_id") != state.user_id:
                return
            notify_clock(state.selected_match_id, build_clock_payload())

        def build_active_players_payload() -> dict:
            return {"player_ids": sorted(state.active_player_ids)}

        def broadcast_active_players() -> None:
            if not state.selected_match_id:
                return
            if not state.selected_match_data:
                return
            if not (state.is_collaborator or state.selected_match_data.get("locked_by_user_id") == state.user_id):
                return
            notify_active_players(state.selected_match_id, build_active_players_payload())

        def is_owner() -> bool:
            if not state.selected_match_data:
                return False
            return state.selected_match_data.get("locked_by_user_id") == state.user_id

        def can_edit_match() -> bool:
            if state.is_match_finalized:
                return False
            return is_owner() or state.is_collaborator

        async def on_action_event():
            await refresh_actions_table()

        def on_join_request(requester_username: str):
            ui.notify(f"{requester_username} wants to join this match", type="warning")
            ui.timer(0, lambda: load_join_requests(requests_table), once=True)
            collaboration_controls.refresh()
            collaboration_status.refresh()

        def on_join_decision(payload: dict):
            if payload.get("match_id") != state.selected_match_id:
                return
            approved = payload.get("approved")
            owner = payload.get("owner_username")
            if approved:
                state.is_collaborator = True
                ui.notify(f"Join approved by {owner}", type="positive")
                collaboration_controls.refresh()
                collaboration_status.refresh()
                render_actions()
                render_players(state.players)
                result_buttons.refresh()
            else:
                ui.notify(f"Join denied by {owner}", type="warning")
                collaboration_controls.refresh()
                collaboration_status.refresh()
                result_buttons.refresh()
            ui.timer(0, refresh_collaboration_state, once=True)

        def on_clock_event(payload: dict):
            if payload.get("period_minutes"):
                state.period_minutes = payload.get("period_minutes")
            if payload.get("total_periods"):
                state.total_periods = payload.get("total_periods")
            state.clock_running = bool(payload.get("clock_running"))
            if payload.get("clock_seconds") is not None:
                state.clock_seconds = int(payload.get("clock_seconds"))
            if payload.get("remaining_seconds") is not None:
                state.remaining_seconds = int(payload.get("remaining_seconds"))
            if payload.get("period") is not None:
                state.period = int(payload.get("period"))
            if payload.get("is_finalized") is not None:
                if state.selected_match_data is None:
                    state.selected_match_data = {}
                state.selected_match_data["is_finalized"] = bool(payload.get("is_finalized"))
                if state.selected_match_data["is_finalized"]:
                    state.clock_running = False
                    state.current_action = None
                    state.selected_player_id = None
            if payload.get("locked_by_user_id") is not None:
                if state.selected_match_data is None:
                    state.selected_match_data = {}
                state.selected_match_data["locked_by_user_id"] = payload.get("locked_by_user_id")
                collaboration_controls.refresh()
                collaboration_status.refresh()
                ui.timer(0, refresh_collaboration_state, once=True)
                render_actions()
                render_players(state.players)
                result_buttons.refresh()
            if state.clock_display:
                state.clock_display.text = state.formatted_remaining_time
            clock_area.refresh()
            if payload.get("is_finalized") is not None:
                render_actions()
                render_players(state.players)

        def on_active_players_event(payload: dict):
            player_ids = payload.get("player_ids") or []
            state.active_player_ids = set(player_ids)
            render_players(state.players)

        async def request_join_match():
            if not state.selected_match_id:
                return
            try:
                await controller.request_join(state.selected_match_id, token=state.api_token)
                ui.notify("Join request sent", type="positive")
                collaboration_controls.refresh()
            except Exception as exc:
                ui.notify(f"Failed to request join: {exc}", type="negative")

        async def refresh_collaboration_state():
            if not state.selected_match_id:
                state.owner_username = None
                state.collaborator_usernames = []
                collaboration_controls.refresh()
                collaboration_status.refresh()
                return
            data = await controller.load_collaborators(state.selected_match_id, token=state.api_token)
            owner = data.get("owner") or {}
            state.owner_username = owner.get("username")
            state.collaborator_usernames = [
                c.get("username")
                for c in data.get("collaborators", [])
                if c.get("username")
            ]
            collaboration_controls.refresh()
            collaboration_status.refresh()

        async def unlock_match(match_id: int) -> None:
            await controller.unlock_match(match_id, token=state.api_token)
        
        async def finalize_match():
            """Finalize the current match"""
            if not state.selected_match_id:
                return
            if not is_owner():
                ui.notify("Only the match owner can finalize", type="warning")
                return
            if state.clock_running:
                ui.notify("Pause the clock before finalizing the match", type="warning")
                return
            
            try:
                match_data = await controller.finalize_match(token=state.api_token)
                if not match_data:
                    return
                state.selected_match_data = match_data
                state.clock_running = False
                logger.info(f"Match {state.selected_match_id} finalized")
                if state.locked_match_id:
                    await unlock_match(state.locked_match_id)
                    state.locked_match_id = None
                
                # Refresh UI to show finalized state
                clock_area.refresh()
                render_actions()
                render_players(state.players)
                broadcast_clock_state()
                
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
                ui.label("Match Settings").classes("text-lg font-bold")
                minutes_input = ui.number(label="Minutes per half", value=state.period_minutes, min=1)
                halves_input = ui.number(label="Number of halves", value=state.total_periods, min=1)

                def save():
                    if state.clock_running:
                        ui.notify("Pause the clock before changing settings", type="warning")
                        return
                    controller.apply_match_settings(
                        int(minutes_input.value),
                        int(halves_input.value),
                    )
                    clock_area.refresh()
                    set_time_dialog.close()
                    broadcast_clock_state()

                ui.button("Save", on_click=save)

        def toggle_clock():
            if state.is_match_finalized:
                ui.notify("Cannot modify clock for a finalized match", type="warning")
                return
            if not is_owner():
                ui.notify("Only the match owner can control the clock", type="warning")
                return
            if not controller.toggle_clock():
                ui.notify("Reset the clock before starting", type="warning")
                return
            clock_area.refresh()
            broadcast_clock_state()

        def tick():
            controller.tick(
                update_player_time_labels,
                lambda message: ui.notify(message, type="warning"),
                clock_area.refresh,
            )
            if state.clock_running:
                broadcast_clock_state()


        def reset_clock():
            if state.is_match_finalized:
                ui.notify("Cannot reset clock for a finalized match", type="warning")
                return
            if not is_owner():
                ui.notify("Only the match owner can reset the clock", type="warning")
                return
            controller.reset_clock()
            clock_area.refresh()
            broadcast_clock_state()

        def set_clock_dialog():
            if state.is_match_finalized:
                ui.notify("Cannot set time for a finalized match", type="warning")
                return
            if not is_owner():
                ui.notify("Only the match owner can change settings", type="warning")
                return
            set_time_dialog.open()
        
        # create the timer
        controller.ensure_timer(tick)


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
                await api_post("/actions", action_data, token=state.api_token)
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
            await refresh_actions_table()
            persist_live_state()


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
            state.clock_running = False
            state.clock_seconds = 0
            state.period = 1
            state.remaining_seconds = state.period_minutes * 60
            state.is_collaborator = False
            state.owner_username = None
            state.collaborator_usernames = []

            players_column.clear()
            if state.locked_match_id:
                await unlock_match(state.locked_match_id)
                state.locked_match_id = None
            clock_area.refresh()
            collaboration_controls.refresh()
            collaboration_status.refresh()
            persist_live_state()


        async def on_match_change(match_id):
            # Save playtime for previous match if exists
            if state.selected_match_id and not state.is_match_finalized:
                await save_playtime_data()

            if state.selected_match_id:
                unsubscribe_actions(state.selected_match_id, ui.context.client)
                unsubscribe_joins(state.selected_match_id, ui.context.client)
                unsubscribe_clock(state.selected_match_id, ui.context.client)
                unsubscribe_active_players(state.selected_match_id, ui.context.client)

            if state.locked_match_id:
                await unlock_match(state.locked_match_id)
                state.locked_match_id = None
            
            state.selected_match_id = match_id
            state.selected_match_data = None
            players_column.clear()
            state.is_collaborator = False

            logger.info(f"Switching match to {match_id}")
            if match_id is None:
                # Reset state
                state.saved_player_seconds = {}
                state.player_seconds = {}
                state.clock_seconds = 0
                state.period = 1
                state.remaining_seconds = state.period_minutes * 60
                state.team_score = 0
                state.opponent_score = 0
                state.is_collaborator = False
                state.owner_username = None
                state.collaborator_usernames = []
                clock_area.refresh()
                await refresh_actions_table()
                collaboration_controls.refresh()
                collaboration_status.refresh()
                persist_live_state()
                return
            
            # Load match data (including finalized status)
            await load_match_data(match_id)
            clock_area.refresh()

            if state.is_match_finalized:
                state.clock_running = False
                if state.locked_match_id:
                    await unlock_match(state.locked_match_id)
                    state.locked_match_id = None
            else:
                await lock_match(match_id)
                collaboration_controls.refresh()
                collaboration_status.refresh()
            
            # Load playtime data
            await load_playtime_data(match_id)
            
            # Load players
            state.players = await load_team_players(state.selected_team_id)
            state.active_player_ids = set()  # Reset active players
            state.player_seconds = {}  # Reset current session times
            period_seconds = max(1, state.period_minutes * 60)
            elapsed_in_period = state.clock_seconds % period_seconds
            state.remaining_seconds = max(0, period_seconds - elapsed_in_period)

            render_actions()
            render_players(state.players)
            clock_area.refresh()
            await refresh_actions_table()
            await refresh_collaboration_state()
            result_buttons.refresh()
            persist_live_state()

            subscribe_actions(state.selected_match_id, ui.context.client, on_action_event)
            subscribe_clock(state.selected_match_id, ui.context.client, on_clock_event)
            subscribe_active_players(state.selected_match_id, ui.context.client, on_active_players_event)
            if state.selected_match_data and state.selected_match_data.get("locked_by_user_id") == state.user_id:
                subscribe_joins(state.selected_match_id, ui.context.client, on_join_request)
            
            # Start auto-save timer (save every 30 seconds)
            if state.playtime_save_timer:
                state.playtime_save_timer.deactivate()
            if not state.is_match_finalized:
                state.playtime_save_timer = ui.timer(30.0, lambda: save_playtime_data(), active=True)

        async def handle_disconnect():
            if state.locked_match_id:
                await unlock_match(state.locked_match_id)
                state.locked_match_id = None
            if state.selected_match_id:
                unsubscribe_actions(state.selected_match_id, ui.context.client)
                unsubscribe_joins(state.selected_match_id, ui.context.client)
                unsubscribe_clock(state.selected_match_id, ui.context.client)
                unsubscribe_active_players(state.selected_match_id, ui.context.client)
            user_id = state.user_id
            if user_id:
                unsubscribe_join_decisions(user_id, ui.context.client)


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

        def update_player_time_labels():
            if not state.players:
                return
            labels = getattr(state, "player_time_labels", {})
            if not labels:
                return
            for pid, label in labels.items():
                label.text = state.formatted_player_time(pid)

        # simple handler for clicking a player button (when enabled)
        def on_player_button_click(player_id):
            if not can_edit_match():
                return
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
            persist_live_state()


        # Switch handler
        async def on_switch_handler(e, pid, button):
            if not can_edit_match():
                ui.notify("Match is locked by another user", type="warning")
                e.value = not e.value
                return
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
            broadcast_active_players()
            persist_live_state()


        def render_actions():
            action_column.clear()

            with action_column:
                for action_type in ActionType:
                    if action_type == ActionType.OPPONENT_GOAL:
                        continue
                    act_btn = ActionButton(
                        action_type,
                        action_type == state.current_action,
                        on_click=on_action_button_click
                    )
                    if state.is_match_finalized or not can_edit_match():
                        act_btn.disable()


        def render_players(players):
            players_column.clear()
            state.player_time_labels = {}
 
            with players_column:
                with ui.grid(columns=2).classes("gap-4"):
                    def player_sort_key(player):
                        return (
                            player["id"] not in state.active_player_ids,
                            player.get("last_name", ""),
                            player.get("first_name", ""),
                        )

                    def render_player_card(player):
                        player_id = player["id"]
                        player_name = f"{player.get('first_name', 'Unknown')} ({player.get('number', '')})"
                        is_active = player_id in state.active_player_ids
                        is_selected = (state.selected_player_id == player_id)

                        with ui.grid().classes("grid-cols-[auto_3rem_4rem] items-center gap-2"):
                            btn = PlayerButton(
                                player_id=player_id,
                                player_name=player_name,
                                active=is_active,
                                selected=is_selected,
                                on_click=on_player_button_click,
                            )
                            player_switch = ui.switch(
                                value=is_active,
                                on_change=lambda e, pid=player_id, button=btn: on_switch_handler(e, pid, button),
                            )
                            if state.is_match_finalized or not can_edit_match():
                                player_switch.disable()
                                btn.disable()

                            time_label = ui.label(state.formatted_player_time(player_id)).classes("text-xs text-grey-6")
                            state.player_time_labels[player_id] = time_label

                    female_players = [p for p in players if p.get("sex") == "female"]
                    male_players = [p for p in players if p.get("sex") == "male"]

                    with ui.column().classes("gap-2"):
                        for p in sorted(female_players, key=player_sort_key):
                            render_player_card(p)

                    with ui.column().classes("gap-2"):
                        for p in sorted(male_players, key=player_sort_key):
                            render_player_card(p)

        def update_scores_from_actions(actions):
            team_score = 0
            opponent_score = 0
            goal_actions = {
                ActionType.SHOT,
                ActionType.KORTE_KANS,
                ActionType.VRIJWORP,
                ActionType.STRAFWORP,
                ActionType.INLOPER,
            }
            for action in actions:
                if action.get("is_opponent"):
                    opponent_score += 1
                elif action.get("result") and action.get("action") in {a.value for a in goal_actions}:
                    team_score += 1
            state.team_score = team_score
            state.opponent_score = opponent_score
            clock_area.refresh()

        async def refresh_actions_table():
            if not state.selected_match_id:
                actions_table.rows = []
                actions_table.update()
                return
            actions = await controller.load_match_actions(state.selected_match_id, token=state.api_token)
            players_by_id = {p["id"]: p for p in state.players}

            def format_time(seconds: int) -> str:
                mins, secs = divmod(seconds, 60)
                return f"{mins:02d}:{secs:02d}"

            rows = []
            for action in sorted(actions, key=lambda a: (a.get("timestamp", 0), a.get("id", 0)), reverse=True):
                player = players_by_id.get(action.get("player_id"))
                player_name = "Opponent" if action.get("is_opponent") else (
                    f'{player.get("first_name", "")} {player.get("last_name", "")}'.strip() if player else str(action.get("player_id"))
                )
                action_label = format_action_label(action.get("action") or "")
                result_label = "Score" if action.get("result") else "Miss"
                x_val = action.get("x")
                y_val = action.get("y")
                x_fmt = round(x_val, 1) if isinstance(x_val, (int, float)) else x_val
                y_fmt = round(y_val, 1) if isinstance(y_val, (int, float)) else y_val
                rows.append({
                    "id": action.get("id"),
                    "action": action_label,
                    "player_name": player_name,
                    "username": action.get("username"),
                    "timestamp": format_time(action.get("timestamp", 0)),
                    "period": action.get("period"),
                    "x": x_fmt,
                    "y": y_fmt,
                    "result": result_label,
                    "_raw": action,
                })
            update_scores_from_actions(actions)
            actions_table.rows = rows
            actions_table.update()

        def open_edit_action_dialog(e):
            if state.is_match_finalized:
                ui.notify("Cannot edit actions for a finalized match", type="warning")
                return

            row = e.args
            raw = row.get("_raw", {})
            with ui.dialog() as dialog:
                with ui.card():
                    ui.label("Edit action").classes("text-lg font-bold")
                    action_select = ui.select(
                        {a.value: a.name.replace("_", " ").title() for a in ActionType},
                        value=raw.get("action"),
                        label="Action type",
                    )
                    player_select = ui.select(
                        {0: "Opponent", **{p["id"]: f'{p.get("first_name", "")} {p.get("last_name", "")}' for p in state.players}},
                        value=raw.get("player_id") or 0,
                        label="Player",
                    )
                    time_input = ui.number(label="Time (seconds)", value=raw.get("timestamp", 0), min=0)
                    period_input = ui.number(label="Half", value=raw.get("period", 1), min=1)
                    x_input = ui.number(label="X coordinate", value=raw.get("x"))
                    y_input = ui.number(label="Y coordinate", value=raw.get("y"))
                    result_toggle = ui.switch("Score", value=bool(raw.get("result")))
                    is_opponent_toggle = ui.switch("Opponent goal", value=bool(raw.get("is_opponent")))

                    async def save():
                        is_opponent = bool(is_opponent_toggle.value)
                        player_id = None if is_opponent or player_select.value == 0 else player_select.value
                        payload = {
                            "match_id": state.selected_match_id,
                            "player_id": player_id,
                            "timestamp": int(time_input.value or 0),
                            "x": x_input.value,
                            "y": y_input.value,
                            "period": int(period_input.value or 1),
                            "action": action_select.value,
                            "result": bool(result_toggle.value),
                            "is_opponent": is_opponent,
                        }
                        try:
                            await controller.update_action(raw.get("id"), payload, token=state.api_token)
                            dialog.close()
                            await refresh_actions_table()
                        except Exception as exc:
                            ui.notify(f"Failed to update action: {exc}", type="negative")

                    ui.button("Save", on_click=save)

        async def delete_action(e):
            if state.is_match_finalized:
                ui.notify("Cannot delete actions for a finalized match", type="warning")
                return
            row = e.args
            raw = row.get("_raw", {})
            try:
                await controller.delete_action(raw.get("id"), token=state.api_token)
                await refresh_actions_table()
            except Exception as exc:
                ui.notify(f"Failed to delete action: {exc}", type="negative")

        async def register_opponent_goal():
            if state.is_match_finalized:
                ui.notify("Cannot add actions to a finalized match", type="warning")
                return
            if not state.selected_match_id:
                return
            action_data = {
                "match_id": state.selected_match_id,
                "player_id": None,
                "timestamp": state.clock_seconds,
                "x": None,
                "y": None,
                "period": state.period,
                "action": ActionType.OPPONENT_GOAL,
                "result": True,
                "is_opponent": True,
            }
            try:
                await api_post("/actions", action_data, token=state.api_token)
            except Exception as exc:
                ui.notify(f"Failed to add opponent goal: {exc}", type="negative")
                return
            await refresh_actions_table()

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
                    def decrement_period():
                        if not is_owner():
                            ui.notify("Only the match owner can change the half", type="warning")
                            return
                        state.period = max(1, state.period - 1)
                        clock_area.refresh()

                    def increment_period():
                        if not is_owner():
                            ui.notify("Only the match owner can change the half", type="warning")
                            return
                        state.period += 1
                        clock_area.refresh()

                    period_minus = ui.button("-", on_click=decrement_period).props("round sm")
                    ui.label(f"P{state.period}").classes("text-xl font-bold mx-2")
                    period_plus = ui.button("+", on_click=increment_period).props("round sm")
                    
                    if state.is_match_finalized:
                        period_minus.disable()
                        period_plus.disable()
                    
                    ui.separator().props("vertical").classes("mx-4")
                    
                    # Time Display
                    state.clock_display = ui.label(state.formatted_remaining_time).classes("text-4xl font-mono font-bold mx-4 bg-black text-red-500 px-2 rounded")
                    
                    ui.separator().props("vertical").classes("mx-4")

                    # Controls
                    clock_button = None
                    if state.clock_running:
                        clock_button = ui.button("PAUSE", on_click=toggle_clock, color="warning", icon="pause")
                    else:
                        clock_button = ui.button("START", on_click=toggle_clock, color="positive", icon="play_arrow")
                    
                    if state.is_match_finalized:
                        clock_button.disable()
                    team_score = getattr(state, "team_score", 0)
                    opponent_score = getattr(state, "opponent_score", 0)
                    location = (state.selected_match_data or {}).get("location", "") or ""
                    is_home = location.strip().lower() == "thuis"
                    score_text = f"{team_score} - {opponent_score}" if is_home else f"{opponent_score} - {team_score}"
                    ui.separator().props("vertical").classes("mx-4")
                    ui.label(score_text).classes("text-4xl font-bold")
                    opp_button = ui.button("Opp Goal", on_click=register_opponent_goal, color="orange").classes("ml-2")
                    if state.is_match_finalized or not can_edit_match():
                        opp_button.disable()
                    settings_btn = ui.button(icon="settings", color="grey").props("flat round")
                    with settings_btn:
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
                    if state.selected_match_id and not state.is_match_finalized:
                        ui.button(
                            "Finalize Match",
                            on_click=finalize_match,
                            color="red",
                            icon="lock",
                        ).classes("ml-2")

        @ui.refreshable
        def collaboration_controls():
            if not state.selected_match_id or state.is_match_finalized:
                return
            if state.selected_match_data and state.selected_match_data.get("locked_by_user_id") == state.user_id:
                ui.button("Join Requests", on_click=open_join_requests).props("flat")
                return
            if state.locked_match_id:
                return
            if getattr(state, "is_collaborator", False):
                return
            if state.selected_match_data and state.selected_match_data.get("locked_by_user_id"):
                ui.button("Request to join", on_click=request_join_match).props("flat")

        @ui.refreshable
        def collaboration_status():
            if not state.selected_match_id:
                return
            if is_owner():
                ui.label("Owner: You").classes("text-xs text-grey-7")
                if state.collaborator_usernames:
                    ui.label(f"Connected: {', '.join(state.collaborator_usernames)}").classes("text-xs text-grey-7")
                return
            if state.owner_username:
                ui.label(f"Owner: {state.owner_username}").classes("text-xs text-grey-7")

        async def load_join_requests(table):
            data = await controller.load_join_requests(state.selected_match_id, token=state.api_token)
            table.rows = [
                {"id": item["requester"]["id"], "username": item["requester"]["username"]}
                for item in data
            ]
            table.update()

        def open_join_requests():
            ui.timer(0, lambda: load_join_requests(requests_table), once=True)
            join_requests_dialog.open()

                    

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
        user_id = state.user_id
        if user_id:
            subscribe_join_decisions(user_id, ui.context.client, on_join_decision)
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
            with ui.tabs().props("dense") as tabs:
                ui.tab("Live")
                ui.tab("Events")
            with ui.row().classes("items-center gap-3"):
                collaboration_controls()
                collaboration_status()


        with ui.row():
            clock_area()
        with ui.dialog() as join_requests_dialog:
            with ui.card():
                ui.label("Join requests").classes("text-lg font-bold")
                requests_table = ui.table(
                    columns=[
                        {"name": "username", "label": "User", "field": "username", "align": "left"},
                        {"name": "actions", "label": "Actions", "field": "id", "classes": "auto-width"},
                    ],
                    rows=[],
                    row_key="id",
                ).classes("w-full mt-2 q-table--dense")

                async def accept_request(row_id):
                    await controller.decide_join(state.selected_match_id, row_id, True)
                    await load_join_requests(requests_table)
                    broadcast_clock_state()
                    broadcast_active_players()
                    await refresh_collaboration_state()

                async def deny_request(row_id):
                    await controller.decide_join(state.selected_match_id, row_id, False)
                    await load_join_requests(requests_table)
                    await refresh_collaboration_state()

                requests_table.add_slot('body-cell', '''
                <q-td :props="props">
                    <template v-if="props.col.name === 'actions'">
                        <q-btn flat dense round icon="check" color="green" @click="() => $parent.$emit('accept', props.row.id)" />
                        <q-btn flat dense round icon="close" color="red" @click="() => $parent.$emit('deny', props.row.id)" />
                    </template>
                    <template v-else>
                        {{ props.value }}
                    </template>
                </q-td>''')
                requests_table.on("accept", lambda e: accept_request(e.args))
                requests_table.on("deny", lambda e: deny_request(e.args))
                ui.button("Close", on_click=join_requests_dialog.close)

        with ui.tab_panels(tabs, value="Live").classes("w-full"):
            with ui.tab_panel("Live"):
                state.voice_enabled = False

                async def on_voice_toggle(e):
                    enabled = bool(e.value)
                    state.voice_enabled = enabled
                    if not enabled:
                        voice_status.text = "Voice: Off"
                        voice_timer.active = False
                        await ui.run_javascript("""
                            window.__voice_enabled = false;
                            if (window.__voice_recognition) {
                                try { window.__voice_recognition.stop(); } catch (e) {}
                            }
                        """)
                        return

                    supported = await ui.run_javascript(
                        "return !!(window.SpeechRecognition || window.webkitSpeechRecognition)"
                    )
                    if not supported:
                        ui.notify("Voice input is not supported in this browser", type="warning")
                        state.voice_enabled = False
                        voice_status.text = "Voice: Off"
                        e.value = False
                        return

                    voice_status.text = "Voice: On"
                    voice_timer.active = True
                    await ui.run_javascript("""
                        window.__voice_queue = window.__voice_queue || [];
                        window.__voice_enabled = true;
                        if (!window.__voice_recognition) {
                            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                            const rec = new SpeechRecognition();
                            rec.lang = 'nl-NL';
                            rec.continuous = true;
                            rec.interimResults = false;
                            rec.onresult = (event) => {
                                for (let i = event.resultIndex; i < event.results.length; i++) {
                                    if (event.results[i].isFinal) {
                                        window.__voice_queue.push(event.results[i][0].transcript);
                                    }
                                }
                            };
                            rec.onend = () => {
                                if (window.__voice_enabled) {
                                    try { rec.start(); } catch (e) {}
                                }
                            };
                            rec.onerror = () => {
                                if (window.__voice_enabled) {
                                    try { rec.stop(); } catch (e) {}
                                }
                            };
                            window.__voice_recognition = rec;
                        }
                        try { window.__voice_recognition.start(); } catch (e) {}
                    """)

                with ui.row().classes("items-center gap-3"):
                    ui.switch("Voice input", on_change=on_voice_toggle)
                    voice_status = ui.label("Voice: Off").classes("text-xs text-grey-6")
                    ui.label(
                        "Zeg: actie speler resultaat (bv. 'schot jan ok'). "
                        "Acties: schot, korte kans, vrije worp, strafworp, inloper, rebound, assist/steun, steal. "
                        "Resultaat: ok/score of gemist/mis."
                    ).classes("text-xs text-grey-6")
                voice_timer = ui.timer(0.5, poll_voice_queue, active=False)

                with ui.row().classes("items-start gap-4"):
                    with ui.card():
                        ui.label("Actions").classes("text-xs font-bold text-grey-6")
                        action_column = ui.row().classes("items-center gap-2 flex-wrap")
                    with ui.card():
                        ui.label("Result").classes("text-xs font-bold text-grey-6")
                        @ui.refreshable
                        def result_buttons():
                            with ui.row().classes("items-center gap-2"):
                                ok_button = ui.button(
                                    "Ok / Score",
                                    on_click=lambda x: submit(True),
                                    icon="thumb_up"
                                )
                                miss_button = ui.button(
                                    "Gemist",
                                    on_click=lambda x: submit(False),
                                    icon="thumb_down"
                                )
                                if state.is_match_finalized or not can_edit_match():
                                    ok_button.disable()
                                    miss_button.disable()
                        result_buttons()

                with ui.row().classes("items-start gap-4"):
                    src = 'korfball_field.svg'
                    #src = 'korfball.svg'
                    #ii = ui.interactive_image(src, on_mouse=mouse_handler, events=['mousedown', 'mouseup'], cross=True)
                    with ui.card():
                        ui.label("Playfield").classes("text-xs font-bold text-grey-6")
                        ii = ui.interactive_image(
                            src,
                            on_mouse=mouse_handler,
                            events=['mousedown'],
                            sanitize=False,
                        ).style('width: 600px; height: auto')
                    with ui.card():
                        ui.label("Players").classes("text-xs font-bold text-grey-6")
                        players_column = ui.column()

            with ui.tab_panel("Events"):
                with ui.card().classes("w-full"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("Match events").classes("text-xs font-bold text-grey-6")
                        ui.button("Refresh", on_click=refresh_actions_table).props("flat")
                    actions_table = ui.table(
                        columns=[
                            {'name': 'actions', 'label': 'Actions', 'field': 'id', 'classes': 'auto-width no-wrap'},
                            {"name": "action", "label": "Action", "field": "action", "align": 'left'},
                            {"name": "player_name", "label": "Player", "field": "player_name", "align": 'left'},
                            {"name": "username", "label": "User", "field": "username", "align": 'left'},
                            {"name": "timestamp", "label": "Time", "field": "timestamp", "align": 'right'},
                            {"name": "period", "label": "Half", "field": "period", "align": 'right'},
                            {"name": "x", "label": "X", "field": "x", "align": 'right'},
                            {"name": "y", "label": "Y", "field": "y", "align": 'right'},
                            {"name": "result", "label": "Result", "field": "result", "align": 'left'},
                        ],
                        rows=[],
                        row_key="id",
                        column_defaults={'align': 'left', 'headerClasses': 'text-primary'},
                        pagination={'rowsPerPage': 12},
                    ).classes("w-full mt-2 q-table--dense")
                    actions_table.add_slot('body-cell', '''
                    <q-td :props="props">
                        <template v-if="props.col.name === 'actions'">
                            <q-btn flat dense round icon="edit" @click="() => $parent.$emit('edit', props.row)" />
                            <q-btn flat dense round icon="delete" color="red" @click="() => $parent.$emit('delete', props.row)" />
                        </template>
                        <template v-else>
                            {{ props.value }}
                        </template>
                    </q-td>''')
                    actions_table.on("edit", open_edit_action_dialog)
                    actions_table.on("delete", delete_action)




        # ---------------------------------------------------------------
        # INITIAL LOAD
        # ---------------------------------------------------------------
        async def refresh_all():
            await load_teams()
            await restore_live_state()

        ui.timer(0, refresh_all, once=True)

    apply_layout(content, page_title="Match Actions")
