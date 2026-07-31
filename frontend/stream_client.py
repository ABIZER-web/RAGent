"""
Threaded streaming client for the frontend.
Streamlit runs a script top-to-bottom per interaction and can't process a
button click while the script is blocked on a network read — so a "Stop"
button can't work if we just loop over requests.iter_content() directly.

Instead: the actual HTTP streaming happens in a background thread that
writes chunks into a thread-safe queue and can be told to stop via a
threading.Event. The Streamlit script polls the queue in short bursts and
reruns itself rapidly, which lets Streamlit process the Stop button click
in between polls.
"""

import threading
import queue
import requests


class StreamHandle:
    def __init__(self):
        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.done = False
        self.error = None

    def request_stop(self):
        self.stop_event.set()


def start_stream(url: str, data: dict, timeout: int = 120) -> StreamHandle:
    """Starts a background thread streaming the response; returns a handle to poll."""
    handle = StreamHandle()

    def worker():
        try:
            with requests.post(url, data=data, stream=True, timeout=timeout) as res:
                for chunk in res.iter_content(chunk_size=None, decode_unicode=True):
                    if handle.stop_event.is_set():
                        handle.q.put("\n\n⏹️ Generation stopped by user.")
                        break
                    if chunk:
                        handle.q.put(chunk)
        except Exception as e:
            handle.error = str(e)
        finally:
            handle.done = True

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return handle


def drain_queue(handle: StreamHandle) -> str:
    """Pulls everything currently available from the queue without blocking."""
    pieces = []
    try:
        while True:
            pieces.append(handle.q.get_nowait())
    except queue.Empty:
        pass
    return "".join(pieces)
