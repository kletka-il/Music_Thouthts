"""Сборка macOS-приложения Music_Thoughts.app через PyInstaller.

Запуск:
    python3 build_mac.py

Скрипт сам создаёт виртуальное окружение в .venv-build/, ставит туда
PyInstaller, Flask и pywebview, и собирает .app — Homebrew Python не трогается.

Результат: dist/Music_Thoughts.app — открывается двойным кликом в Finder.
"""



import os

import sys

import subprocess

import shutil

import venv



ROOT = os.path.dirname(os.path.abspath(__file__))

VENV_DIR = os.path.join(ROOT, ".venv-build")





def venv_python():

    return os.path.join(VENV_DIR, "bin", "python")





def ensure_venv():

    py = venv_python()

    if not os.path.isfile(py):

        print(">> Создаю виртуальное окружение в .venv-build/ ...")

        venv.EnvBuilder(with_pip=True, clear=False).create(VENV_DIR)

    subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])



    print(">> Устанавливаю зависимости в venv ...")

    pkgs = ["pyinstaller", "pywebview", "flask"]

    req = os.path.join(ROOT, "requirements.txt")

    if os.path.isfile(req):

        subprocess.check_call([py, "-m", "pip", "install", "-r", req, "--quiet"])

    subprocess.check_call([py, "-m", "pip", "install", *pkgs, "--quiet"])





def main():

    if sys.platform != "darwin":

        print("Этот скрипт предназначен для macOS. На Windows используйте build_exe.py")

        sys.exit(1)



    ensure_venv()

    py = venv_python()



    dist_dir = os.path.join(ROOT, "dist")

    build_dir = os.path.join(ROOT, "build")

    spec_file = os.path.join(ROOT, "Music_Thoughts.spec")

    for path in (dist_dir, build_dir):

        if os.path.isdir(path):

            shutil.rmtree(path, ignore_errors=True)

    if os.path.isfile(spec_file):

        os.remove(spec_file)



    args = [

        py, "-m", "PyInstaller",

        "--noconfirm",

        "--clean",

        "--name", "Music_Thoughts",

        "--windowed",

        "--osx-bundle-identifier", "com.music.thoughts",

        "--add-data", "templates:templates",

        "--add-data", "static:static",

        "--hidden-import", "flask",

        "--hidden-import", "werkzeug",

        "--hidden-import", "webview",

        "--hidden-import", "webview.platforms.cocoa",

        "--collect-all", "webview",

        os.path.join(ROOT, "desktop_app.py"),

    ]

    print(">>", " ".join(args))

    subprocess.check_call(args, cwd=ROOT)



    app_path = os.path.join(dist_dir, "Music_Thoughts.app")

    if os.path.isdir(app_path):

        print(f"\nГотово! Приложение: {app_path}")

        print("Запуск: двойной клик по Music_Thoughts.app в Finder")

        print("Или из терминала: open dist/Music_Thoughts.app")

    else:

        print("\nСборка завершена, но .app не найден. Проверьте dist/")





if __name__ == "__main__":

    main()

