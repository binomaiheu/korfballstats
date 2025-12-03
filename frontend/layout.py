from nicegui import ui

def apply_layout(content):
    """Wrap a page in the shared layout."""

    left_drawer = ui.left_drawer()\
        .props('behavior=mobile persistent bordered')\
        .classes('bg-blue-100')


    with ui.header().classes(replace='row items-center').style('height: 50px;'):
        ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
        ui.label("Ganda Korfball Stats").style('margin-left: 16px; font-weight: bold; font-size: 18px; color: white;')

    with left_drawer:
        with ui.row().classes('justify-end'):
            ui.button(icon='close', on_click=left_drawer.toggle).props('flat round dense')
    
        ui.link('Teams', '/teams')
        ui.link('Matches', '/matches')
        ui.link('Live feed', '/live')

#    with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
#        ui.button(on_click=footer.toggle, icon='contact_support').props('fab')

    # insert page content
    content()