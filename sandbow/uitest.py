from nicegui import ui

# ---------------------------
# Example Data
# ---------------------------
players = [
    {"id": 1, "name": "Alice", "team": None},
    {"id": 2, "name": "Bob", "team": None},
    {"id": 3, "name": "Charlie", "team": "Red"},
    {"id": 4, "name": "Daphne", "team": "Blue"},
]

teams = ["Red", "Blue", "Green"]

# Helpers
def get_players_in_team(team):
    return [p for p in players if p["team"] == team]

def get_unassigned_players():
    return [p for p in players if p["team"] is None]


# ---------------------------
# UI
# ---------------------------
ui.label('Team Assignment').classes('text-2xl font-bold mb-4')

selected_team = ui.select(teams, label="Select Team", value=teams[0]) \
                  .classes('mb-4')

columns = [
    {'name': 'name', 'label': 'Player', 'field': 'name'},
]

with ui.row().classes('w-full gap-8'):

    # LEFT TABLE — Unassigned
    left_table = ui.table(
        columns=columns,
        rows=get_unassigned_players(),
        selection='multiple',
        title='Unassigned Players'
    ).classes('w-1/2')

    # RIGHT TABLE — Assigned to selected team
    right_table = ui.table(
        columns=columns,
        rows=get_players_in_team(selected_team.value),
        selection='multiple',
        title='Players in Team'
    ).classes('w-1/2')


# ---------------------------
# Refresh Logic
# ---------------------------
def refresh_tables():
    left_table.rows = get_unassigned_players()
    right_table.rows = get_players_in_team(selected_team.value)
    left_table.update()
    right_table.update()


selected_team.on('update:model-value', lambda e: refresh_tables())


# ---------------------------
# Transfer Functions
# ---------------------------
def add_selected():
    for row in left_table.selected:
        row['team'] = selected_team.value
    refresh_tables()

def remove_selected():
    for row in right_table.selected:
        row['team'] = None
    refresh_tables()


# Buttons
with ui.row().classes('items-center justify-center gap-4 mt-4'):
    ui.button('→ Add to Team', on_click=add_selected)
    ui.button('← Remove from Team', on_click=remove_selected)


ui.run()
