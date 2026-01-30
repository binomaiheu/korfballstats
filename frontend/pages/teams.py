import logging
import httpx
from nicegui import ui

from frontend.layout import apply_layout
from frontend.api import api_get, api_post, api_delete, api_put

from backend.schema import SexType

logger = logging.getLogger('uvicorn.error')


@ui.page('/teams')
def teams_page():

    def content():
        
        async def refresh_all():
            await refresh_team_table()
            await refresh_player_table()
            await refresh_selects()
            await refresh_assignment_tables()

        async def refresh_team_table():
            team_table.rows = await api_get("/teams")

        async def refresh_player_table():
            player_table.rows = await api_get("/players")

        async def refresh_selects():
            teams = await api_get("/teams")

            assign_team.set_options({t["id"] : t["name"] for t in teams})



        async def refresh_assignment_tables():
            left_table.rows = []
            right_table.rows = []
            selected_team_id = assign_team.value


            if selected_team_id is not None:
                team = await api_get(f"/teams/{selected_team_id}?with_players=true")
                if team:
                    right_table.props(f'title="Players in {team['name']}"')
                    assigned_player_ids = {p["id"] for p in team.get("players", [])}
                    all_players = await api_get("/players")
                    left_table.rows = [p for p in all_players if p["id"] not in assigned_player_ids]
                    right_table.rows = [p for p in all_players if p["id"] in assigned_player_ids]

            left_table.update()
            right_table.update()



        async def add_to_team():
            selected_team_id = assign_team.value

            for player in left_table.selected:
                await api_post(
                    "/teams/assign",
                    {"team_id": selected_team_id, "player_id": player['id']},
                )
            await refresh_assignment_tables()

        async def remove_from_team():
            selected_team_id = assign_team.value

            for player in right_table.selected:
                await api_post(
                    "/teams/unassign",
                    {"team_id": selected_team_id, "player_id": player['id']},
                )
            await refresh_assignment_tables()



        async def open_add_player_dialog():        
            with ui.dialog().classes('w-2/3') as dialog, ui.card().classes('w-full'):
                ui.label('Add new player').classes('text-xl mb-2')
                with ui.row().classes('w-full'):
                    first_name = ui.input('First Name').classes('w-70')
                    last_name = ui.input('Last Name').classes('w-70')
                    number = ui.input('Number').classes('w-70')
                    sex = ui.select(label='Sex', options={'male': 'Male', 'female': 'Female'}).classes('w-70')
                with ui.row():
                    ui.button('Save', on_click=lambda: save_player(first_name.value, last_name.value, number.value, sex.value, dialog))
                    ui.button('Cancel', on_click=dialog.close)
            dialog.open()

        async def save_player(first_name, last_name, number, sex, dialog):
            try:
                if first_name.strip() and last_name.strip() and number.strip() and sex.strip():
                    await api_post("/players", {"first_name": first_name, "last_name": last_name, "number": number, "sex": sex})
                    dialog.close()
                    await refresh_all()
            except httpx.HTTPStatusError as e:
                # Show error message from response, if available
                try:
                    error_detail = e.response.json().get('detail', str(e))
                except Exception:
                    error_detail = str(e)
                ui.notify(f"Failed to update player: {error_detail}", color='negative')
            except Exception as e:
                ui.notify(f"Unexpected error: {e}", color='negative')

        async def open_edit_player_dialog(p):
            player = p.args
            with ui.dialog().classes('w-2/3') as dialog, ui.card().classes('w-full'):
                ui.label('Edit player').classes('text-xl mb-2')
                with ui.row().classes('w-full'):
                    first_name = ui.input('First Name', value=player['first_name']).classes('w-70')
                    last_name = ui.input('Last Name', value=player['last_name']).classes('w-70')
                    number = ui.input('Number', value=str(player['number'])).classes('w-70')
                    sex = ui.select(label='Sex', options={'male': 'Male', 'female': 'Female'}, value=player['sex']).classes('w-70')
                with ui.row():
                    ui.button('Save', on_click=lambda: save_edited_player(player['id'], first_name.value, last_name.value, number.value, sex.value, dialog))
                    ui.button('Cancel', on_click=dialog.close)
            dialog.open()

        async def save_edited_player(player_id, first_name, last_name, number, sex, dialog):
            try:
                if first_name.strip() and last_name.strip() and number.strip():
                    await api_put(f"/players/{player_id}", {"first_name": first_name, "last_name": last_name, "number": number, "sex": sex})
                    dialog.close()
                    await refresh_all()
            except httpx.HTTPStatusError as e:
                # Show error message from response, if available
                try:
                    error_detail = e.response.json().get('detail', str(e))
                except Exception:
                    error_detail = str(e)
                ui.notify(f"Failed to update player: {error_detail}", color='negative')
            except Exception as e:
                ui.notify(f"Unexpected error: {e}", color='negative')


        async def delete_player(p):
            player = p.args
            
            async def confirm_delete():
                try:
                    await api_delete(f"/players/{player['id']}")
                    await refresh_all()
                except httpx.HTTPStatusError as e:
                    # Show error message from response, if available
                    try:
                        error_detail = e.response.json().get('detail', str(e))
                    except Exception:
                        error_detail = str(e)
                    ui.notify(f"Failed to delete player: {error_detail}", color='negative')
                except Exception as e:
                    ui.notify(f"Unexpected error: {e}", color='negative')
                confirm_dialog.close()

            with ui.dialog() as confirm_dialog, ui.card():
                ui.label(f"Are you sure you want to delete player {player['first_name']} {player['last_name']}?")
                with ui.row():
                    ui.button('Yes, delete', color='red', on_click=confirm_delete)
                    ui.button('Cancel', on_click=confirm_dialog.close)
            confirm_dialog.open()


        async def open_add_team_dialog():
            with ui.dialog().classes('w-2/3') as dialog, ui.card().classes('w-full'):
                ui.label('Add new team').classes('text-xl mb-2')
                with ui.row().classes('w-full'):
                    name = ui.input('Team Name').classes('w-70')
                with ui.row():
                    ui.button('Save', on_click=lambda: save_team(name.value, dialog))
                    ui.button('Cancel', on_click=dialog.close)
            dialog.open()

        async def save_team(name, dialog):
            try:
                if name.strip():
                    await api_post("/teams", {"name": name})
                    dialog.close()
                    await refresh_all()
            except httpx.HTTPStatusError as e:
                # Show error message from response, if available
                try:
                    error_detail = e.response.json().get('detail', str(e))
                except Exception:
                    error_detail = str(e)
                ui.notify(f"Failed to update team: {error_detail}", color='negative')
            except Exception as e:
                ui.notify(f"Unexpected error: {e}", color='negative')
        
        async def open_edit_team_dialog(p):
            team = p.args
            with ui.dialog().classes('w-2/3') as dialog, ui.card().classes('w-full'):
                ui.label('Edit team').classes('text-xl mb-2')
                with ui.row().classes('w-full'):
                    name = ui.input('Team Name', value=team['name']).classes('w-70')
                with ui.row():
                    ui.button('Save', on_click=lambda: save_edited_team(team['id'], name.value, dialog))
                    ui.button('Cancel', on_click=dialog.close)
            dialog.open()

        async def save_edited_team(team_id, name, dialog):
            try:
                if name.strip():
                    await api_put(f"/teams/{team_id}", {"name": name})
                    dialog.close()
                    await refresh_all()
            except httpx.HTTPStatusError as e:
                # Show error message from response, if available
                try:
                    error_detail = e.response.json().get('detail', str(e))
                except Exception:
                    error_detail = str(e)
                ui.notify(f"Failed to update team: {error_detail}", color='negative')
            except Exception as e:
                ui.notify(f"Unexpected error: {e}", color='negative')


        async def delete_team(p):
            team = p.args
            
            async def confirm_delete():
                try:
                    await api_delete(f"/teams/{team['id']}")
                    await refresh_all()
                except httpx.HTTPStatusError as e:
                    # Show error message from response, if available
                    try:
                        error_detail = e.response.json().get('detail', str(e))
                    except Exception:
                        error_detail = str(e)
                    ui.notify(f"Failed to delete team: {error_detail}", color='negative')
                except Exception as e:
                    ui.notify(f"Unexpected error: {e}", color='negative')
                confirm_dialog.close()

            with ui.dialog() as confirm_dialog, ui.card():
                ui.label(f"Are you sure you want to delete team {team['name']}?")
                with ui.row():
                    ui.button('Yes, delete', color='red', on_click=confirm_delete)
                    ui.button('Cancel', on_click=confirm_dialog.close)
            confirm_dialog.open()


        # ----------------------------------------------------------------------
        # UI LAYOUT
        # ----------------------------------------------------------------------

        # title moved to header
        ui.markdown("Here you can enter the players in your club and assign them to different teams. The players can be assigned to multiple teams.")

        with ui.grid(columns=2).classes('w-full gap-4'):

            # Full-width item
            with ui.card().classes('col-span-2'):
                # ===================================================================
                # Assign players to teams
                # ===================================================================
                ui.label('Assign players')

                assign_team = ui.select([], label="Select team", with_input=False, on_change=refresh_assignment_tables).classes("w-40")

                # Buttons
                with ui.row().classes('w-full justify-between gap-4'):
                    ui.button('→ Add to Team', on_click=add_to_team)
                    ui.button('← Remove from Team', on_click=remove_from_team)

                with ui.row().classes('w-full no-wrap gap-4'):
                    columns = [
                        {'name': 'first_name', 'label': 'First Name', 'field': 'first_name'},
                        {'name': 'last_name', 'label': 'Last Name', 'field': 'last_name'},
                        {'name': 'number', 'label': 'Number', 'field': 'number'},
                        {'name': 'sex', 'label': 'Sex', 'field': 'sex'},
                    ]
                    # LEFT TABLE — Unassigned
                    left_table = ui.table(
                        columns=columns,
                        rows=[],
                        selection='multiple',
                        title='Available'
                    ).classes('flex-1 min-w-0 q-table--dense')

                    # RIGHT TABLE — Assigned to selected team
                    right_table = ui.table(
                        columns=columns,
                        rows=[],
                        selection='multiple',
                        title="Players"
                    ).classes('flex-1 min-w-0 q-table--dense')



            with ui.card():
                # ===================================================================
                # Manage players
                # ===================================================================
                ui.label('Manage players')

                player_table = ui.table(
                    columns=[
                        {'name': 'actions', 'label': 'Actions', 'field': 'id', 'classes': 'auto-width no-wrap'},
                        {"name": "id", "label": "Id", "field": "id", "align": 'left'},
                        {"name": "first_name", "label": "First name", "field": "first_name", "sortable": True, "align": 'left'},
                        {"name": "last_name", "label": "Last name", "field": "last_name", "sortable": True, "align": 'left'},
                        {"name": "number", "label": "Number", "field": "number", "sortable": True, "align": 'right'},
                        {"name": "sex", "label": "Sex", "field": "sex", "sortable": True, "align": 'left'}
                    ],
                    rows=[],
                    row_key="id",
                    column_defaults={
                        'align': 'left',
                        'headerClasses': 'text-primary'
                    },
                    pagination={'rowsPerPage': 10}
                ).classes("w-full mt-2 q-table--dense")
                player_table.add_slot('body-cell', '''
                <q-td :props="props">
                    <template v-if="props.col.name === 'actions'">
                        <q-btn flat dense round icon="edit" @click="() => $parent.$emit('edit', props.row)" />
                        <q-btn flat dense round icon="delete" color="red" @click="() => $parent.$emit('delete', props.row)" />
                    </template>
                    <template v-else>
                        {{ props.value }}
                    </template>
                </q-td>''')

                player_table.on("edit", open_edit_player_dialog)
                player_table.on("delete", delete_player)
                ui.button("Add player", on_click=open_add_player_dialog)


            with ui.card():
                # ===================================================================
                # Manage teams
                # ===================================================================
                ui.label('Manage teams')

                team_table = ui.table(
                    columns=[
                        {'name': 'actions', 'label': 'Actions', 'field': 'id', 'classes': 'auto-width no-wrap'},
                        {"name": "id", "label": "Id", "field": "id", "align": 'left'},
                        {"name": "name", "label": "Name", "field": "name",  "align": 'left'}
                    ],
                    rows=[],
                    row_key="id",
                    column_defaults={
                        'align': 'left',
                        'headerClasses': 'text-primary'
                    },
                    pagination={'rowsPerPage': 10}
                ).classes("w-full mt-2 q-table--dense")
                team_table.add_slot('body-cell', '''
                <q-td :props="props">
                    <template v-if="props.col.name === 'actions'">
                        <q-btn flat dense round icon="edit" @click="() => $parent.$emit('edit', props.row)" />
                        <q-btn flat dense round icon="delete" color="red" @click="() => $parent.$emit('delete', props.row)" />
                    </template>
                    <template v-else>
                        {{ props.value }}
                    </template>
                </q-td>
                ''')
                team_table.on("edit", open_edit_team_dialog)  # Edit handler can be implemented similarly
                team_table.on("delete", delete_team)  # Delete handler can be implemented
                ui.button("Add team", on_click=open_add_team_dialog)



        # ----------------------------------------------------------------------
        # INITIAL DATA LOAD
        # ----------------------------------------------------------------------
        ui.timer(0.1, refresh_all, once=True)


    apply_layout(content, page_title="Player and Team Setup")