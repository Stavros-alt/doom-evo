import os
import subprocess
import sys

# i hate building binaries but here we are.
# it builds both linux and windows binaries.
# you need wine installed for the windows one to work.

def run_command(cmd):
    try:
        subprocess.check_call(cmd)
    except Exception as e:
        print(f"failed to run {' '.join(cmd)}: {e}")

def build():
    # common params. whatever.
    # aggressively excluding a bunch of bloat so the binary isn't 1gb
    excludes = [
        'torch', 'nvidia', 'transformers', 'matplotlib', 'scipy', 'pandas',
        'sklearn', 'unsloth', 'llama_cpp', 'mergekit', 'diffusers', 'datasets',
        'huggingface_hub', 'PyQt6', 'Flask', 'fastapi', 'uvicorn', 'selenium',
        'discord', 'telegram', 'wandb', 'kaggle', 'jedi', 'ipython', 'notebook',
        'ipykernel', 'PIL', 'gi', 'sqlalchemy', 'lxml', 'sympy', 'cryptography',
        'nbformat', 'pyarrow', 'sqlite3', 'email', 'html', 'http', 'xml', 'pydantic'
    ]

    base_params = [
        '--onefile',
        '--windowed',
        '--clean',
        '--collect-all', 'numpy',
        'main.py'
    ]
    for e in excludes:
        base_params.extend(['--exclude-module', e])

    print("--- building linux binary ---")
    run_command(['pyinstaller', '--name=DOOM_EVO_LINUX'] + base_params)

    # trying to fix glibc hell for older distros. i hate linux sometimes.
    print("\n--- applying staticx for linux portability ---")
    try:
        run_command(['staticx', 'dist/DOOM_EVO_LINUX', 'dist/DOOM_EVO'])
        os.remove('dist/DOOM_EVO_LINUX')
    except Exception as e:
        print(f"staticx failed (you might need to install it): {e}")

    print("\n--- building windows binary (requires wine) ---")
    # assuming wine has python installed. if not, whatever.
    run_command(['wine', 'python', '-m', 'PyInstaller', '--name=DOOM_EVO_WIN'] + base_params)

    print("\nfinished. check the 'dist' folder for your binaries.")

if __name__ == "__main__":
    build()
