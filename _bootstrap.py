\
\
\
                                                             



import subprocess

import sys

import importlib

import os



REQUIRED = {

    "flask": "Flask>=3.0.0",

    "werkzeug": "Werkzeug>=3.0.0",

}

OPTIONAL = {

    "webview": "pywebview>=5.0",

}





def _install(spec):

    cmd = [sys.executable, "-m", "pip", "install", "--quiet", spec]

    try:

        subprocess.check_call(cmd)

    except subprocess.CalledProcessError:

        cmd_break = cmd + ["--break-system-packages"]

        subprocess.check_call(cmd_break)





def ensure(modules=None):

    modules = modules or REQUIRED

    missing = []

    for mod, spec in modules.items():

        try:

            importlib.import_module(mod)

        except ImportError:

            missing.append((mod, spec))

    if not missing:

        return

    print(f"[bootstrap] Не хватает пакетов: {[m[0] for m in missing]}. Устанавливаю…", flush=True)

    for mod, spec in missing:

        try:

            _install(spec)

        except Exception as e:

            print(f"[bootstrap] Не удалось поставить {spec}: {e}", file=sys.stderr)

    importlib.invalidate_caches()





def ensure_optional():

    ensure(OPTIONAL)

