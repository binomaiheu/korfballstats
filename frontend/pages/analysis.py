from asyncio import events
import logging
from collections import defaultdict

from nicegui import ui, events

from backend.schema import ActionType
from frontend.api import api_get, api_post
from frontend.layout import apply_layout

from typing import Dict, List, Optional

logger = logging.getLogger('uvicorn.error')

# --- Helper List of ActionTypes that have a success/attempt count ---
# Only include the action types you want to display with S/A format
ATTEMPT_ACTIONS = [
    ActionType.SHOT,
    ActionType.KORTE_KANS,
    ActionType.VRIJWORP,
    ActionType.STRAFWORP,
    ActionType.INLOPER,
]

@ui.page('/analysis')
def analysis_page():

    # Container to hold the overall stats table, allowing us to update it easily
    overall_stats_container = ui.row().classes('w-full') # Initialize container

    def content():

        # ----------------------------------------------------------------------
        # HELPERS
        # ----------------------------------------------------------------------

        async def load_teams():
            teams = await api_get("/teams")
            team_select.set_options({t["id"]: t["name"] for t in teams})

        async def load_matches(team_id=None):
            """Load matches. If team_id is given: filter only that team's matches."""
            if team_id:
                matches = await api_get(f"/teams/{team_id}/matches")
            else:
                matches = await api_get("/matches")

            match_select.set_options({
                m["id"]: f'{m.get("date", "")[:10]} — {m.get("opponent_name", "")} ({m["team"]["name"]})'
                for m in matches
            })

            match_select.value = None  # reset

        # ----------------------------------------------------------------------
        # NEW: OVERALL STATS CALCULATOR
        # ----------------------------------------------------------------------
        def calculate_match_totals(actions: List[Dict]) -> List[Dict]:
            """Calculates total success/attempt/efficiency for the entire match."""
            
            # Initialize totals structure
            totals = {a.value: {"success": 0, "attempts": 0} for a in ActionType}
            
            overall_success = 0
            overall_attempts = 0

            # Count actions
            for a in actions:
                action_type = ActionType(a["action"])

                totals[action_type.value]["attempts"] += 1
                if a["result"]:
                    totals[action_type.value]["success"] += 1

                # Count overall goals/efficiency (using the defined ATTEMPT_ACTIONS)
                if action_type in ATTEMPT_ACTIONS: 
                    overall_attempts += 1
                    if a["result"]:
                        overall_success += 1

            # Transpose and format for the table
            transposed_rows = []
            
            # Add the overall row first
            overall_eff = f"{round(100 * overall_success / overall_attempts, 1)}%" if overall_attempts else "-"
            transposed_rows.append({
                "metric": "Overall",
                "success": overall_success,
                "attempts": overall_attempts,
                "efficiency": overall_eff,
                "display": f"{overall_success}/{overall_attempts} {overall_eff}",
            })
            
            # Add rows for individual actions
            for action_key in sorted(totals.keys()):
                s_count = totals[action_key]["success"]
                a_count = totals[action_key]["attempts"]
                
                if a_count > 0:
                    eff = f"{round(100 * s_count / a_count, 1)}%"
                    display = f"{s_count}/{a_count} ({eff})"
                else:
                    eff = "-"
                    display = "-"

                transposed_rows.append({
                    "metric": action_key.replace("_", " ").title(),
                    "success": s_count,
                    "attempts": a_count,
                    "efficiency": eff,
                    "display": display,
                })

            return transposed_rows


        # ----------------------------------------------------------------------
        # MAIN STATS LOADER (MODIFIED)
        # ----------------------------------------------------------------------
        async def load_statistics(match_id: int):
            if not match_id:
                return

            match = await api_get(f"/matches/{match_id}")
            players = await api_get(f"/teams/{match['team']['id']}/players")
            actions = await api_get(f"/matches/{match_id}/actions")

            # --- 1. Process Player Stats ---
            stats = defaultdict(lambda: {
                "name": "",
                "number": "",
                "actions": {a.value: {"success": 0, "attempts": 0} for a in ActionType},
                "success": 0,
                "attempts": 0,
            })
            
            for p in players:
                stats[p["id"]]["name"] = f"{p['first_name']} {p['last_name']}"
                stats[p["id"]]["number"] = p["number"]

            for a in actions:
                pid = a["player_id"]
                action_type = ActionType(a["action"])

                if pid not in stats: continue

                stats[pid]["actions"][action_type.value]["attempts"] += 1
                if a["result"]:
                    stats[pid]["actions"][action_type.value]["success"] += 1

                if action_type in ATTEMPT_ACTIONS:
                    stats[pid]["attempts"] += 1
                    if a["result"]:
                        stats[pid]["success"] += 1

            table_rows = []
            for pid, s in stats.items():
                row = {
                    "player": s["name"],
                    "nr": s["number"],
                    "goals": s["success"],
                    "efficiency":
                        f"{round(100 * s['success'] / s['attempts'], 1)}%"
                        if s["attempts"] else "-",
                }

                for action in ActionType:
                    action_key = action.value
                    action_stats = s["actions"][action_key]
                    s_count = action_stats["success"]
                    a_count = action_stats["attempts"]

                    row[action_key] = f"{s_count}/{a_count}" if a_count > 0 else "-"
                    row[f'{action_key}_eff'] = (
                        f"({round(100 * s_count / a_count, 1)}%)"
                        if a_count > 0
                        else ""
                    )
                table_rows.append(row)

            stats_table.rows = table_rows
            
            # --- 2. Process Overall Match Stats ---
            overall_rows = calculate_match_totals(actions)
            update_overall_table(overall_rows) # Call new function to update the second table


        # ----------------------------------------------------------------------
        # NEW: OVERALL TABLE RENDERER
        # ----------------------------------------------------------------------
        def update_overall_table(rows: List[Dict]):
            """Clears the container and renders the new overall stats table."""
            overall_stats_table.rows = rows


        # ----------------------------------------------------------------------
        # EVENT HANDLERS
        # ----------------------------------------------------------------------

        async def on_team_change(team_id):
            await load_matches(team_id)

        async def on_match_change(match_id):
            logger.info(f"Selected match ID: {match_id}")
            await load_statistics(match_id)


        # ----------------------------------------------------------------------
        # UI LAYOUT
        # ----------------------------------------------------------------------

        ui.markdown("### 🏷️ Analysis")

        with ui.row().classes("items-center gap-4"):
            team_select = ui.select(
                {},
                label="Select team",
                with_input=False,
                on_change=lambda e: on_team_change(e.value),
            ).classes("w-32")

            match_select = ui.select(
                {},
                label="Select match",
                with_input=False,
                on_change=lambda e: on_match_change(e.value),
            ).classes("w-48")

        with ui.row().classes("items-start gap-8"):
            with ui.card().classes("p-4"):
                ui.label("Overall Statistics").classes("text-xs font-bold text-grey-6")
                # --- NEW: Overall Match Statistics Table ---
                # The table will be rendered inside this container by update_overall_table()
                overall_columns = [
                    {"name": "metric", "label": "Metric", "field": "metric", "align": "left"},
                    {"name": "display", "label": "Efficiency", "field": "display", "align": "left"},
                    # Optional: columns for raw numbers if you want them hidden/available
                    # {"name": "success", "label": "Successes", "field": "success"},
                    # {"name": "attempts", "label": "Attempts", "field": "attempts"},
                    # {"name": "efficiency", "label": "Efficiency", "field": "efficiency"},
                ]
                
                overall_stats_table = ui.table(
                    columns=overall_columns,
                    rows=[],
                    row_key="metric",
                ).classes("w-96 q-table--dense") # Use a fixed width for a cleaner look
        
        with ui.row().classes("items-start gap-8"):
    
            with ui.card().classes("p-4"):
                ui.label("Player Statistics").classes("text-xs font-bold text-grey-6")        
                # Player statistics table
                columns = [
                    {"name": "player", "label": "Player", "field": "player", "align": "left", "sortable": True},
                    {"name": "nr", "label": "Nr", "field": "nr", "align": "left"},
                ] + [
                    {"name": a.value, "label": f'{a.value.replace("_", " ").title()}', "field": a.value, "align": "left", "sortable": True}
                    for a in ActionType
                ] + [
                    {"name": "goals", "label": "Goals", "field": "goals", "align": "left", "sortable": True},
                    {"name": "efficiency", "label": "Overall", "field": "efficiency", "align": "left", "sortable": True},
                ]

                stats_table = ui.table(
                    columns=columns,
                    rows=[],
                    pagination=20,
                    row_key="player"
                ).classes("w-full q-table--dense")

        # ----------------------------------------------------------------------
        # CUSTOM SLOTS FOR S/A
        # ----------------------------------------------------------------------

        for action in ActionType:
            action_key = action.value
            stats_table.add_slot(
                f'body-cell-{action_key}',
                r"""
                <td :props="props">
                    <div v-if="props.row['{{ action_key }}'] !== '-'">
                        <span class="text-weight-bold">
                            {{ props.row['{{ action_key }}'] }}
                        </span>
                        <br>
                        <span class="text-caption">
                            {{ props.row['{{ action_key }}_eff'] }}
                        </span>
                    </div>
                    <div v-else>
                        -
                    </div>
                </td>
                """.replace('{{ action_key }}', action_key)
            )


        # ----------------------------------------------------------------------
        # INITIAL LOAD
        # ----------------------------------------------------------------------

        async def refresh_all():
            await load_teams()

        ui.timer(0, refresh_all, once=True)

    apply_layout(content)