from nicegui import events, ui

def mouse_handler(e: events.MouseEventArguments):
    color = 'Red' 
    ii.content += f'<circle cx="{e.image_x}" cy="{e.image_y}" r="5" fill="none" stroke="{color}" stroke-width="2" />'
    print(f'{e.type} at ({e.image_x:.1f}, {e.image_y:.1f})')

src = 'korfball_field.svg'
#ii = ui.interactive_image(src, on_mouse=mouse_handler, events=['mousedown', 'mouseup'], cross=True)
ii = ui.interactive_image(src, on_mouse=mouse_handler, events=['mousedown'])

ui.run()