from nicegui import app, ui

from frontend.api import api_login, api_me


@ui.page("/login")
def login_page():
    if app.storage.user.get("token"):
        ui.navigate.to("/home")
        return

    async def handle_login():
        try:
            data = await api_login(username_input.value, password_input.value)
        except Exception as exc:
            ui.notify(f"Login failed: {exc}", type="negative")
            return

        app.storage.user["token"] = data.get("access_token")
        app.storage.user["username"] = data.get("username")
        try:
            me = await api_me()
            app.storage.user["user_id"] = me.get("id")
        except Exception:
            app.storage.user.pop("user_id", None)
        ui.notify("Logged in", type="positive")
        ui.navigate.to("/home")

    with ui.column().classes("w-full items-center justify-center mt-12"):
        ui.image("logo_ganda.jpg").classes("w-48")
        ui.label("Login").classes("text-2xl font-bold mt-4")
        username_input = ui.input("Username").classes("w-72")
        password_input = ui.input("Password", password=True, password_toggle_button=True).classes("w-72")
        ui.button("Sign in", on_click=handle_login).classes("w-72")
