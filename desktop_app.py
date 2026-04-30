\
\
\
\
   



import os

import sys

import threading

import time

import socket

import urllib.request



import webview



from app import app

from database import init_db, resolve_listen_urls





def find_free_port(default=5000):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:

        s.bind(("127.0.0.1", default))

        s.close()

        return default

    except OSError:

        s.close()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        s.bind(("127.0.0.1", 0))

        port = s.getsockname()[1]

        s.close()

        return port





def run_server(port):

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)





def wait_for_server(url, timeout=15):

    start = time.time()

    while time.time() - start < timeout:

        try:

            urllib.request.urlopen(url + "/api/health", timeout=1)

            return True

        except Exception:

            time.sleep(0.2)

    return False





def main():

    init_db()

    threading.Thread(target=resolve_listen_urls, daemon=True).start()

    port = find_free_port(5000)

    url = f"http://127.0.0.1:{port}"



    t = threading.Thread(target=run_server, args=(port,), daemon=True)

    t.start()



    if not wait_for_server(url):

        print("Не удалось дождаться запуска сервера", file=sys.stderr)

        sys.exit(1)



    webview.create_window(

        "Music_Thoughts.exe",

        url,

        width=1100,

        height=820,

        resizable=True,

    )

    webview.start()





if __name__ == "__main__":

    main()

