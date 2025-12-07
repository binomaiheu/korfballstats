from nicegui import ui, app
import asyncio
import base64
import logging
from fastapi import WebSocket, WebSocketDisconnect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Global State Management ---
# Map NiceGUI session ID to its audio queue for real-time processing
session_queues = {} 
# Map NiceGUI session ID to a list holding all raw WebM chunks for the current recording
recording_buffers = {} 
# -----------------------------

@ui.page('/')
async def index():
    # 1. Session Setup
    session_id = ui.context.client.id
    audio_queue = asyncio.Queue()
    session_queues[session_id] = audio_queue
    recording_buffers[session_id] = []
    
    # Cleanup when the client disconnects
    ui.context.client.on_disconnect(lambda: session_queues.pop(session_id, None))
    ui.context.client.on_disconnect(lambda: recording_buffers.pop(session_id, None))

    # --- UI Elements and State ---
    ui.label('Real-time audio capture demo')
    text_output = ui.label('Waiting for audio...')
    
    # Local state and UI feedback
    status_label = ui.label('Status: Idle')
    is_recording = False

    def start_recording():
        nonlocal is_recording
        if not is_recording:
            is_recording = True
            recording_buffers[session_id] = [] # Clear previous recording
            status_label.set_text('Status: Recording...')
            ui.run_javascript('start_recorder()') # Trigger JS start function
            logger.info("Recording started.")

    async def stop_and_save_webm():
        """Stops the JS recorder, combines WebM chunks, and writes the raw data to disk."""
        nonlocal is_recording
        if is_recording:
            is_recording = False
            ui.run_javascript('stop_recorder()') # Trigger JS stop function
            status_label.set_text('Status: Combining and Saving WebM...')
            logger.info("Recording stopped. Starting WebM save...")

            # 1. Concatenate all WebM chunks
            combined_webm_data = b"".join(recording_buffers[session_id])
            
            if not combined_webm_data:
                status_label.set_text('Status: Error, no audio recorded.')
                return

            try:
                # 2. Write the raw bytes to a file with the .webm extension
                file_path = f'recording_{session_id}.webm'
                with open(file_path, 'wb') as f:
                    f.write(combined_webm_data)
                
                status_label.set_text(f'Status: Saved raw WebM data to **{file_path}** (playable with FFmpeg/VLC).')
            except Exception as e:
                logger.error(f"Error during WebM file write: {e}")
                status_label.set_text(f'Status: File Save Failed ({e})')
            finally:
                recording_buffers[session_id] = [] # Clear buffer after save
                
    ui.button('Start Recording', on_click=start_recording).classes('mr-2')
    ui.button('Stop and Save WebM', on_click=stop_and_save_webm)
    
    # --- JavaScript Logic (Start/Stop Control) ---
    ui.run_javascript(f'''
        let ws_url = "ws://" + window.location.host + "/ws/audio/{session_id}";
        let ws = new WebSocket(ws_url);
        let rec = null; 
        let stream = null; 
        
        ws.onopen = () => console.log("Custom audio WebSocket connected.");
        ws.onerror = (e) => console.error("Custom audio WebSocket error:", e);

        // Function to start the MediaRecorder, called by Python button
        window.start_recorder = () => {{
            if (rec && rec.state === "recording") return;

            navigator.mediaDevices.getUserMedia({{ audio: true }}).then(s => {{
                stream = s;
                rec = new MediaRecorder(stream, {{mimeType: "audio/webm"}});
                
                rec.ondataavailable = async e => {{
                    if (e.data.size > 0) {{
                        let reader = new FileReader();
                        reader.onload = () => {{
                            // Send the base64 audio chunk over the custom WebSocket
                            ws.send(reader.result.split(',')[1]); 
                        }};
                        reader.readAsDataURL(e.data);
                    }}
                }};
                rec.start(200); // send 200ms chunks
            }}).catch(err => {{
                console.error("Could not access microphone: " + err);
            }});
        }};

        // Function to stop the MediaRecorder, called by Python button
        window.stop_recorder = () => {{
            if (rec && rec.state === "recording") {{
                rec.stop();
                stream.getTracks().forEach(track => track.stop()); // Stop mic access
                rec = null;
                stream = null;
                console.log("MediaRecorder stopped.");
            }}
        }};
    ''')

    # 4. Consumer (Audio processing task)
    async def process_audio():
        logger.info(f"Starting audio processor task for session {session_id}...")
        while True:
            try:
                data = await audio_queue.get()
                
                if isinstance(data, bytes):
                    if is_recording:
                        # Add the chunk to the recording buffer ONLY IF currently recording
                        recording_buffers[session_id].append(data)
                        display_text = f"Recording chunk... Total bytes captured: {sum(len(c) for c in recording_buffers[session_id])} bytes"
                    else:
                        # If not recording, just report chunk size (optional streaming info)
                        display_text = f"Streaming chunk received... Size: {len(data)} bytes"
                else:
                    display_text = f"Received non-byte data: {data}"
                
                text_output.set_text(display_text)
                audio_queue.task_done()
            except Exception as e:
                logger.error(f"Error in audio processing task: {e}")
                break
            
    asyncio.create_task(process_audio())

# --- Custom WebSocket Endpoint for receiving audio (Unchanged) ---

@app.websocket('/ws/audio/{session_id}')
async def audio_socket(ws: WebSocket, session_id: str):
    if session_id not in session_queues:
        return
    
    audio_queue = session_queues[session_id]
    await ws.accept()
    
    try:
        while True:
            base64_chunk = await ws.receive_text()
            try:
                audio_bytes = base64.b64decode(base64_chunk)
                await audio_queue.put(audio_bytes)
            except Exception as e:
                logger.error(f"Failed to decode base64 chunk: {e}")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

ui.run(title='NiceGUI Raw WebM Capture')