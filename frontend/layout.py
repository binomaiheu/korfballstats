from nicegui import app, ui

from frontend.api import api_post

def apply_layout(content):
    """Wrap a page in the shared layout."""
    if not app.storage.user.get("token"):
        ui.navigate.to("/login")
        return

    left_drawer = ui.left_drawer()\
        .props('behavior=mobile persistent bordered')\
        .classes('bg-blue-100')


    async def handle_logout():
        locked_match_id = app.storage.user.get("locked_match_id")
        if locked_match_id:
            try:
                await api_post(f"/matches/{locked_match_id}/unlock", {})
            except Exception:
                pass
        app.storage.user.clear()
        ui.navigate.to("/login")

    with ui.header().classes(replace='row items-center').style('height: 50px;'):
        ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
        ui.label("Ganda Korfball Statistics").style('margin-left: 16px; font-weight: bold; font-size: 18px; color: white;')
        ui.label(f'User: {app.storage.user.get("username", "unknown")}').classes('ml-auto text-white text-sm')
        ui.button(
            "Logout",
            on_click=handle_logout,
        ).props('flat color=white').classes('ml-2')

    with left_drawer:
        with ui.row().classes('justify-end'):
            ui.button(icon='close', on_click=left_drawer.toggle).props('flat round dense')
    
        ui.link('Teams', '/teams')
        ui.link('Matches', '/matches')
        ui.link('Live feed', '/live')
        ui.link('Analysis', '/analysis')

#    with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
#        ui.button(on_click=footer.toggle, icon='contact_support').props('fab')

    # insert page content
    content()