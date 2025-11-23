from nicegui import ui

from frontend.layout import apply_layout
from frontend.api import api_get, api_post


@ui.page('/teams')
def teams_page():

    def content():
        ui.label('Content of Teams')
        
        async def refresh_all():
            await refresh_team_table()
            await refresh_player_table()
            await refresh_selects()
            await refresh_assignments()

        async def refresh_team_table():
            team_table.rows = await api_get("/teams")

        async def refresh_player_table():
            player_table.rows = await api_get("/players")

        async def refresh_selects():
            teams = await api_get("/teams")
            players = await api_get("/players")

            assign_team.set_options({t["id"] : t["name"] for t in teams})
            assign_player_dropdown.set_options({p["id"] : p["name"] for p in players})

        async def refresh_assignments():
            """
            Build a table of all player→team relations.
            We now derive assignments from /teams/ instead of /players/,
            because /players/ does not contain team_id.
            """

            teams = await api_get("/teams")

            rows = []
            for team in teams:
                tname = team["name"]
                for player in team.get("players", []):
                    rows.append({
                        "team": tname,
                        "player": player["name"]
                    })

            assignments_table.rows = rows

        # ----------------------------------------------------------------------
        # ACTION HANDLERS
        # ----------------------------------------------------------------------
        async def add_team():
            if new_team.value.strip():
                await api_post("/teams", {"name": new_team.value})
                new_team.value = ""
                await refresh_all()

        async def add_player():
            if new_player.value.strip():
                await api_post("/players", {"name": new_player.value})
                new_player.value = ""
                await refresh_all()

        async def assign_handler():
            if assign_team.value and assign_player_dropdown.value:
                await api_post(
                    "/teams/assign",
                    {"team_id": assign_team.value, "player_id": assign_player_dropdown.value},
                )
                await refresh_all()

            # ----------------------------------------------------------------------
            # UI LAYOUT
            # ----------------------------------------------------------------------

        ui.markdown("## 🏆 Team setup")

        



        with ui.row().classes("items-center gap-4"):
            new_team = ui.input("New team name")
            ui.button("Add team", on_click=add_team)

        team_table = ui.table(
            columns=[
                {"name": "id", "label": "ID", "field": "id"},
                {"name": "name", "label": "Name", "field": "name"},
            ],
            rows=[],
            row_key="id",
        ).classes("w-full mt-2")

        ui.separator()

        ui.markdown("## 👤 Players")

        with ui.row().classes("items-center gap-4"):
            new_player = ui.input("New player name")
            ui.button("Add player", on_click=add_player)

        player_table = ui.table(
            columns=[
                {"name": "id", "label": "ID", "field": "id"},
                {"name": "name", "label": "Name", "field": "name"},
            ],
            rows=[],
            row_key="id",
        ).classes("w-full mt-2")

        ui.separator()

        ui.markdown("## 🔗 Assign Players to Teams")

        with ui.row().classes("gap-4"):
            assign_team = ui.select([], label="Team", with_input=False)
            assign_player_dropdown = ui.select([], label="Player", with_input=False)

        ui.button("Assign", on_click=assign_handler).classes("mt-2")

        ui.separator()

        ui.markdown("## 📋 Team Assignments")

        assignments_table = ui.table(
            columns=[
                {"name": "team", "label": "Team", "field": "team"},
                {"name": "player", "label": "Player", "field": "player"},
            ],
            rows=[],
            row_key="team",
            column_defaults={
                'align': 'left',
                'headerClasses': 'text-primary',
            },
            pagination={'rowsPerPage': 20}
        ).classes("w-full")


        # ----------------------------------------------------------------------
        # INITIAL DATA LOAD
        # ----------------------------------------------------------------------
        ui.timer(0, refresh_all, once=True)


    apply_layout(content)