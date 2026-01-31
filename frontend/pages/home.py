from nicegui import ui

from frontend.layout import apply_layout


@ui.page("/home")
def home_page():
    def content():
        with ui.column().classes("w-full items-center"):
            ui.image("logo_ganda.jpg").classes("w-64")
            ui.label("Welcome to Ganda Korfball Statistics").classes("text-2xl font-bold mt-4")
            ui.markdown(
                "Track live match events, manage teams and players, and analyze performance. "
                "Use the Live tab during matches to record actions and playtime, and review "
                "events or make corrections from the Events tab.\n\n"
                "Live matches use a match owner with optional collaborators. If a match is "
                "already open, request to join; once approved you can enter actions while "
                "the owner controls the clock and finalization."
            ).classes("max-w-2xl mt-2 text-center")

    apply_layout(content, page_title="Home")
