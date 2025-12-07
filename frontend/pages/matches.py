import logging

import httpx
from nicegui import ui
from frontend.layout import apply_layout
from frontend.api import api_get, api_post, api_put, api_delete

logger = logging.getLogger('uvicorn.error')


@ui.page('/matches')
def matches_page():
    def content():
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
            team_id = team_select.value
            matches = await api_get(f"/teams/{team_id}/matches") if team_id else []
            # flatten team name for the table
            for m in matches:
                m["team_name"] = m["team"]["name"] if m.get("team") else "N/A"
                m["date"] = m["date"][:10]  # show only date part

            matches_table.rows = matches

        # ----------------------------------------------------------------------
        # ACTION HANDLERS
        # ----------------------------------------------------------------------
        async def create_new_match(team_id, date, opponent_name, location, dialog):
            try:
                if team_id and opponent_name.strip():
                    logger.info(f"Match date: {date}")
                    await api_post(
                        "/matches",
                        {
                            "team_id": team_id,
                            "date": date,
                            "opponent_name": opponent_name,
                            "location": location
                        },
                    )
                    dialog.close()
                    await refresh_all()
            except httpx.HTTPStatusError as e:
                # Show error message from response, if available
                try:
                    error_detail = e.response.json().get('detail', str(e))
                except Exception:
                    error_detail = str(e)
                ui.notify(f"Failed to add match: {error_detail}", color='negative')
            except Exception as e:
                ui.notify(f"Unexpected error: {e}", color='negative')

        async def open_add_match_dialog():
            if team_select.value is None:
                ui.notify("Please select a team first", color='negative')
                return

            team_label = team_select.options.get(team_select.value, "Unknown")
            
            with ui.dialog().classes('w-2/3') as dialog, ui.card().classes('w-full'):
                ui.label(f'Add new {team_label} match').classes('text-xl mb-2')
                with ui.row().classes('w-full'):
                    match_date_diag = ui.date_input('Match Date').classes('w-70')
                    opponent_input_diag = ui.input('Opponent Name').classes('w-70')
                    location_input_diag = ui.select(options=['Thuis', 'Uit'], label='Location').classes('w-70')
                with ui.row():
                    ui.button('Save', on_click=lambda: create_new_match(team_select.value, match_date_diag.value, opponent_input_diag.value, location_input_diag.value, dialog))
                    ui.button('Cancel', on_click=dialog.close)
            dialog.open()

        
        async def open_edit_match_dialog(p):
            if team_select.value is None:
                ui.notify("Please select a team first", color='negative')
                return

            match = p.args
            with ui.dialog().classes('w-2/3') as dialog, ui.card().classes('w-full'):
                ui.label('Edit match').classes('text-xl mb-2')
                with ui.row().classes('w-full'):
                    team_options = {team['id']: team['name'] for team in await api_get("/teams")}
                    team_select_diag = ui.select(team_options, label="Team", with_input=False).classes("w-32")
                    team_select_diag.set_value(match['team']['id'] if match.get('team') else None)
                    match_date_diag = ui.date_input('Match Date').classes('w-70')
                    match_date_diag.set_value(match['date'])
                    opponent_input_diag = ui.input('Opponent Name').classes('w-70')
                    opponent_input_diag.set_value(match['opponent_name'])
                    location_input_diag = ui.select(options=['Thuis', 'Uit'], label='Location').classes('w-70')
                    location_input_diag.set_value(match['location'])
                with ui.row():
                    ui.button('Save', on_click=lambda: save_edited_match(match['id'], team_select_diag.value, match_date_diag.value, opponent_input_diag.value, location_input_diag.value, dialog))
                    ui.button('Cancel', on_click=dialog.close)
            dialog.open()

        async def save_edited_match(match_id, team_id, date, opponent_name, location, dialog):
            try:
                if opponent_name.strip():
                    await api_put(f"/matches/{match_id}", {"team_id": team_id, "date": date, "opponent_name": opponent_name, "location": location})
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


        async def delete_match(p):
            match = p.args

            async def confirm_delete():
                try:
                    await api_delete(f"/matches/{match['id']}")
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
                ui.label(f"Are you sure you want to delete match {match['id']}?")
                with ui.row():
                    ui.button('Yes, delete', color='red', on_click=confirm_delete)
                    ui.button('Cancel', on_click=confirm_dialog.close)
            confirm_dialog.open()



        # ----------------------------------------------------------------------
        # UI LAYOUT
        # ----------------------------------------------------------------------

        ui.markdown("### 🏟️ Matches")

        with ui.card().classes('w-full p-4 mb-4'):

            with ui.row().classes("items-center gap-4"):
                team_select = ui.select([], label="Team", with_input=False, on_change=refresh_matches_table).classes("w-32")

            with ui.row().classes("items-center"):
                matches_table = ui.table(
                    columns=[
                        {"name": "actions", "label": "Actions", "field": "actions", 'classes': 'auto-width no-wrap' },
                        {"name": "team", "label": "Team", "field": "team_name", "sortable": True, "align": 'left'},
                        {"name": "date", "label": "Date", "field": "date", "sortable": True,  "align": 'left'},
                        {"name": "opponent_name", "label": "Opponent", "field": "opponent_name", "sortable": True,  "align": 'left'},
                        {"name": "location", "label": "Location", "field": "location",  "align": 'left'}
                    ],
                    rows=[],
                    row_key="id",
                    column_defaults={
                        'align': 'left',
                        'headerClasses': 'text-primary'
                    },
                    pagination={'rowsPerPage': 10}
                ).classes("w-full mt-4 q-table--dense")
                matches_table.add_slot('body-cell', '''
                    <q-td :props="props">
                        <template v-if="props.col.name === 'actions'">
                            <q-btn flat dense round icon="edit" @click="() => $parent.$emit('edit', props.row)" />
                            <q-btn flat dense round icon="delete" color="red" @click="() => $parent.$emit('delete', props.row)" />
                        </template>
                        <template v-else>
                            {{ props.value }}
                        </template>
                    </q-td>''')

            matches_table.on("edit", open_edit_match_dialog)
            matches_table.on("delete", delete_match)

            ui.button("Add match", on_click=open_add_match_dialog)


        # ----------------------------------------------------------------------
        # INITIAL LOAD
        # ----------------------------------------------------------------------

        ui.timer(0, refresh_all, once=True)


    # setting layout for this content
    apply_layout(content)