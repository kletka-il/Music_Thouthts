\
\
\
\
\
\
\
   



import os

import sys

import subprocess



ROOT = os.path.dirname(os.path.abspath(__file__))





def main():

    sep = ";" if os.name == "nt" else ":"

    args = [

        sys.executable, "-m", "PyInstaller",

        "--noconfirm",

        "--name", "Music_Thoughts",

        "--windowed",

        "--add-data", f"templates{sep}templates",

        "--add-data", f"static{sep}static",

        "--hidden-import", "flask",

        "--hidden-import", "werkzeug",

        "--hidden-import", "webview",

        os.path.join(ROOT, "desktop_app.py"),

    ]

    print(">>", " ".join(args))

    subprocess.check_call(args, cwd=ROOT)

    print("\nГотово. Бинарник лежит в dist/Music_Thoughts/")

    if os.name == "nt":

        print("Запускайте Music_Thoughts.exe")





if __name__ == "__main__":

    main()

