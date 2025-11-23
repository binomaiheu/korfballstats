from nicegui import ui

def apply_layout(content):
    """Wrap a page in the shared layout."""
    with ui.header().classes(replace='row items-center'):
        ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
        ui.label("Korfball Stats")
#    with ui.footer(value=False) as footer:
#        ui.label('Footer')

    with ui.left_drawer().classes('bg-blue-100') as left_drawer:
        with ui.row().classes('justify-end'):
            ui.button(icon='close', on_click=left_drawer.toggle).props('flat round dense')
    
        ui.label('Navigation')
        ui.link('Teams', '/teams')
        ui.link('Matches', '/matches')
        ui.link('Live feed', '/live')

#    with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
#        ui.button(on_click=footer.toggle, icon='contact_support').props('fab')

    # insert page content
    content()