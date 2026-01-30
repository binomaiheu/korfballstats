import logging
from typing import Dict, List, Optional, Callable, Awaitable

from nicegui import app, ui

from frontend.api import api_delete, api_get, api_post, api_put

logger = logging.getLogger('uvicorn.error')


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
        self.period_minutes: int = 25
        self.total_periods: int = 2
        self.remaining_seconds: int = 25 * 60
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

    @property
    def formatted_remaining_time(self):
        mins, secs = divmod(max(0, self.remaining_seconds), 60)
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


class LiveController:
    def __init__(self):
        self.state = LiveState()

    def ensure_timer(self, tick_cb: Callable[[], None]) -> None:
        if self.state.timer is None:
            self.state.timer = ui.timer(1.0, tick_cb)

    async def load_teams(self):
        return await api_get("/teams")

    async def load_matches(self, team_id: Optional[int] = None):
        if team_id:
            return await api_get(f"/teams/{team_id}/matches")
        return await api_get("/matches")

    async def load_team_players(self, team_id: int):
        try:
            return await api_get(f"/teams/{team_id}/players")
        except Exception:
            return []

    async def load_match_data(self, match_id: int):
        try:
            match_data = await api_get(f"/matches/{match_id}")
            self.state.selected_match_data = match_data
            self.state.period = match_data.get("current_period", self.state.period)
            self.state.period_minutes = match_data.get("period_minutes", self.state.period_minutes)
            self.state.total_periods = match_data.get("total_periods", self.state.total_periods)
            return match_data
        except Exception as e:
            logger.error(f"Failed to load match data: {e}")
            return None

    async def load_playtime_data(self, match_id: int):
        try:
            playtime_data = await api_get(f"/playtime/{match_id}")
            self.state.saved_player_seconds = {
                pp["player_id"]: pp["time_played"]
                for pp in playtime_data.get("player_playtimes", [])
            }
            self.state.clock_seconds = playtime_data.get("match_time_registered_s", 0)
            period_seconds = max(1, self.state.period_minutes * 60)
            elapsed_in_period = self.state.clock_seconds % period_seconds
            self.state.remaining_seconds = max(0, period_seconds - elapsed_in_period)
            return playtime_data
        except Exception as e:
            logger.error(f"Failed to load playtime data: {e}")
            self.state.saved_player_seconds = {}
            return None

    async def save_playtime_data(self):
        if not self.state.selected_match_id or self.state.is_match_finalized:
            return

        try:
            total_player_times = {}
            for player_id in set(list(self.state.saved_player_seconds.keys()) + list(self.state.player_seconds.keys())):
                saved = self.state.saved_player_seconds.get(player_id, 0)
                current = self.state.player_seconds.get(player_id, 0)
                total_player_times[player_id] = saved + current

            time_update = {
                "match_time_registered_s": self.state.clock_seconds,
                "player_time_registered_s": total_player_times,
                "current_period": self.state.period,
                "period_minutes": self.state.period_minutes,
                "total_periods": self.state.total_periods,
            }

            await api_put(f"/playtime/{self.state.selected_match_id}", time_update)
            logger.info(f"Saved playtime data: {time_update}")

            self.state.saved_player_seconds = total_player_times
            self.state.player_seconds = {}
        except Exception as e:
            logger.error(f"Failed to save playtime data: {e}")

    async def lock_match(self, match_id: int):
        try:
            await api_post(f"/matches/{match_id}/lock", {})
            self.state.locked_match_id = match_id
            app.storage.user["locked_match_id"] = match_id
            return True, None
        except Exception as e:
            detail = str(e)
            if e.args and isinstance(e.args[0], dict):
                detail = e.args[0].get("detail", detail)
            return False, detail

    async def unlock_match(self, match_id: int):
        try:
            await api_post(f"/matches/{match_id}/unlock", {})
        except Exception:
            return
        app.storage.user.pop("locked_match_id", None)

    async def finalize_match(self):
        if not self.state.selected_match_id:
            return None
        await self.save_playtime_data()
        try:
            match_data = await api_post(f"/matches/{self.state.selected_match_id}/finalize", {})
            self.state.selected_match_data = match_data
            return match_data
        except Exception as e:
            logger.error(f"Failed to finalize match: {e}")
            raise

    async def load_match_actions(self, match_id: int):
        return await api_get(f"/matches/{match_id}/actions")

    async def update_action(self, action_id: int, payload: dict):
        return await api_put(f"/actions/{action_id}", payload)

    async def delete_action(self, action_id: int):
        await api_delete(f"/actions/{action_id}")

    def apply_match_settings(self, minutes: int, halves: int):
        self.state.period_minutes = minutes
        self.state.total_periods = halves
        self.state.period = 1
        self.state.clock_seconds = 0
        self.state.remaining_seconds = self.state.period_minutes * 60

    def toggle_clock(self) -> bool:
        if self.state.is_match_finalized:
            return False
        if self.state.remaining_seconds <= 0:
            return False
        self.state.clock_running = not self.state.clock_running
        return True

    def reset_clock(self) -> bool:
        if self.state.is_match_finalized:
            return False
        self.state.clock_running = False
        self.state.clock_seconds = 0
        self.state.period = 1
        self.state.remaining_seconds = self.state.period_minutes * 60
        return True

    def tick(
        self,
        update_players: Callable[[], None],
        notify: Callable[[str], None],
        refresh_clock: Callable[[], None],
    ) -> None:
        if self.state.clock_running and self.state.remaining_seconds > 0:
            self.state.remaining_seconds -= 1
            self.state.clock_seconds += 1
            if self.state.clock_display:
                self.state.clock_display.text = self.state.formatted_remaining_time

            for pid in self.state.active_player_ids:
                self.state.player_seconds[pid] = self.state.player_seconds.get(pid, 0) + 1

            if self.state.players:
                update_players()

            if self.state.remaining_seconds == 0:
                self.state.clock_running = False
                if self.state.period < self.state.total_periods:
                    self.state.period += 1
                    self.state.remaining_seconds = self.state.period_minutes * 60
                    notify("Half ended. Ready for next half.")
                else:
                    notify("Match time ended.")
                refresh_clock()


def get_live_controller() -> LiveController:
    client = ui.context.client
    if not hasattr(client, "live_controller"):
        client.live_controller = LiveController()
    return client.live_controller
