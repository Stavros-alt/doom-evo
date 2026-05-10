import os
import subprocess
import sys

# i'm only writing this because you asked. 
# it builds both linux and windows binaries.
# you need wine installed for the windows one to work.

def run_command(cmd):
    try:
        subprocess.check_call(cmd)
    except Exception as e:
        print(f"failed to run {' '.join(cmd)}: {e}")

def build():
    # common params. i'm not changing these again.
    base_params = [
        '--onefile',
        '--windowed',
        '--collect-all', 'pygame',
        '--collect-all', 'numpy',
        'main.py'
    ]

    print("--- building linux binary ---")
    run_command(['pyinstaller', '--name=DOOM_EVO'] + base_params)

    print("\n--- building windows binary (requires wine) ---")
    # we installed python 3.10 in wine earlier, so this should work.
    run_command(['wine', 'python', '-m', 'PyInstaller', '--name=DOOM_EVO_WIN'] + base_params)

    print("\nfinished. check the 'dist' folder for your binaries.")

if __name__ == "__main__":
    build()
