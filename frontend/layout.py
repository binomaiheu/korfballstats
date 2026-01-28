from nicegui import app, ui

from frontend.api import api_change_password, api_post

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

    async def submit_password_change():
        if not current_password.value or not new_password.value or not confirm_password.value:
            ui.notify("Please fill in both fields", type="warning")
            return
        if new_password.value != confirm_password.value:
            ui.notify("New passwords do not match", type="warning")
            return
        if len(new_password.value) < 8:
            ui.notify("Password must be at least 8 characters", type="warning")
            return
        if not any(ch.isalpha() for ch in new_password.value):
            ui.notify("Password must include at least one letter", type="warning")
            return
        if not any(ch.isdigit() for ch in new_password.value):
            ui.notify("Password must include at least one number", type="warning")
            return
        if not any(not ch.isalnum() for ch in new_password.value):
            ui.notify("Password must include at least one special character", type="warning")
            return
        try:
            await api_change_password(current_password.value, new_password.value)
        except Exception as exc:
            ui.notify(f"Password change failed: {exc}", type="negative")
            return
        current_password.value = ""
        new_password.value = ""
        confirm_password.value = ""
        password_dialog.close()
        ui.notify("Password updated", type="positive")

    with ui.dialog() as password_dialog:
        with ui.card():
            ui.label("Change password").classes("text-lg font-bold")
            current_password = ui.input("Current password", password=True, password_toggle_button=True)
            new_password = ui.input("New password", password=True, password_toggle_button=True)
            confirm_password = ui.input("Confirm new password", password=True, password_toggle_button=True)
            ui.button("Update password", on_click=submit_password_change)

    with ui.header().classes(replace='row items-center').style('height: 50px;'):
        ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
        ui.label("Ganda Korfball Statistics").style('margin-left: 16px; font-weight: bold; font-size: 18px; color: white;')
        with ui.button(app.storage.user.get("username", "unknown")).props('flat color=white').classes('ml-auto') as user_button:
            with ui.menu():
                ui.menu_item("Change password", on_click=lambda: password_dialog.open())
                ui.menu_item("Logout", on_click=handle_logout)

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