"""Run with the clean CPython venv and requirements-lock.txt installed.

python build_v18.py --mode console
python build_v18.py --mode windowed
Builds in a fresh ASCII TEMP directory; never copies user settings.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['console', 'windowed'], required=True)
    args = parser.parse_args()
    if sys.prefix == sys.base_prefix or 'conda' in sys.version.lower():
        raise SystemExit('Use a clean standalone CPython venv, not Conda/base Python.')
    project = Path(__file__).resolve().parent
    build = Path(tempfile.mkdtemp(prefix='gongwen_v18_'))
    source = build / 'main.py'
    main_source = project / '公文小助手_v18.py'
    if not main_source.exists():
        main_source = project / 'gongwen_helper.py'
    shutil.copy2(main_source, source)
    shutil.copy2(project / 'icon.ico', build / 'icon.ico')
    excluded = 'numpy pandas scipy matplotlib IPython notebook torch torchvision torchaudio tensorflow transformers cv2 sklearn numba llvmlite sympy whisper PyQt5 PyQt6 PySide2 PySide6'.split()
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--onedir', '--noupx', '--' + args.mode, '--name', 'gongwen_helper',
               '--icon', str(build / 'icon.ico'), '--add-data', str(build / 'icon.ico') + ';.',
               '--collect-data', 'DrissionPage', '--collect-data', 'pdfminer',
               '--collect-data', 'tldextract', '--workpath', str(build / 'work'),
               '--distpath', str(build / 'dist'), '--specpath', str(build)]
    for name in excluded:
        command += ['--exclude-module', name]
    command.append(str(source))
    log = build / 'build.log'
    with log.open('w', encoding='utf-8') as f:
        result = subprocess.run(command, cwd=build, stdout=f, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(f'Build failed: {log}')
    app = build / 'dist' / 'gongwen_helper'
    internal = app / '_internal'
    # Bundle matching Tcl/Tk data from the selected interpreter (never mix versions).
    base = Path(sys.base_prefix)
    for src, dest in [('tcl8.6', '_tcl_data'), ('tk8.6', '_tk_data')]:
        shutil.copytree(base / 'tcl' / src, internal / dest, dirs_exist_ok=True)
    system = Path(os.environ['SystemRoot']) / 'System32'
    for name in ['vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'ucrtbase.dll']:
        shutil.copy2(system / name, internal / name)
    for required in ['vcruntime140_1.dll', '_tk_data/tk.tcl', '_tcl_data/init.tcl', 'python311.dll']:
        if not (internal / required).is_file():
            raise SystemExit(f'Missing dependency: {required}')
    if list(app.rglob('settings.json')):
        raise SystemExit('Refusing package containing user settings')
    total = sum(p.stat().st_size for p in app.rglob('*') if p.is_file())
    if total > 150 * 1024 * 1024:
        raise SystemExit(f'Package too large: {total} bytes')
    report = {'mode': args.mode, 'app': str(app), 'log': str(log), 'bytes': total,
              'python': sys.version, 'excluded': excluded}
    (project.parent / '_temp').mkdir(exist_ok=True)
    result_file = project.parent / '_temp' / f'v18_build_{args.mode}.json'
    result_file.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
