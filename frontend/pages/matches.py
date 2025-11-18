from nicegui import ui
from frontend.api import api_get, api_post


def matches_page():

    # ----------------------------------------------------------------------
    # REFRESH HELPERS
    # ----------------------------------------------------------------------

    async def refresh_all():
        await refresh_team_select()
        await refresh_matches_table()

    async def refresh_team_select():
        teams = await api_get("/teams")
        team_select.set_options({t["id"]: t["name"] for t in teams})

    async def refresh_matches_table():
        teams = {t["id"]: t["name"] for t in await api_get("/teams")}
        matches = await api_get("/matches")

        # enrich with readable team names
        for m in matches:
            m["team_name"] = teams.get(m["team_id"], "Unknown")

        matches_table.rows = matches

    # ----------------------------------------------------------------------
    # ACTION HANDLERS
    # ----------------------------------------------------------------------

    async def create_new_match():
        if team_select.value and opponent_input.value.strip():
            await api_post(
                "/matches",
                {
                    "team_id": team_select.value,
                    "opponent_name": opponent_input.value,
                    "date": match_date.value,
                },
            )
            opponent_input.value = ""
            match_date.value = None
            await refresh_all()

    # ----------------------------------------------------------------------
    # UI LAYOUT
    # ----------------------------------------------------------------------

    ui.markdown("## 🏟️ Matches")

    with ui.row().classes("items-center gap-4"):
        match_date = ui.date_input("Match date")
        team_select = ui.select([], label="Team", with_input=False)
        opponent_input = ui.input("Opponent team name")
        ui.button("Create match", on_click=create_new_match)

    matches_table = ui.table(
        columns=[
            {"name": "id", "label": "ID", "field": "id"},
            {"name": "team_name", "label": "Team", "field": "team_name"},
            {"name": "opponent_name", "label": "Opponent", "field": "opponent_name"},
            {"name": "date", "label": "Date", "field": "date"},
        ],
        rows=[],
        row_key="id",
    ).classes("w-full mt-4")

    # ----------------------------------------------------------------------
    # INITIAL LOAD
    # ----------------------------------------------------------------------

    ui.timer(0, refresh_all, once=True)
