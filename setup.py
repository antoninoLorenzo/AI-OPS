from setuptools import setup, find_packages
from pathlib import Path
from cli import VERSION

CURRENT_DIRECTORY = Path(__file__).parent

# Setup Requirements
REQUIREMENTS_PATH = str(
    CURRENT_DIRECTORY / 'cli' / 'requirements.txt'
)
REQUIREMENTS = []
with open(REQUIREMENTS_PATH, 'r') as fp:
    lines = fp.read().splitlines()
    if lines:
        REQUIREMENTS.extend(lines)

setup(
    name='ai-ops-cli',
    version=VERSION,
    author='@antoninoLorenzo',
    url='https://github.com/antoninoLorenzo/AI-OPS',

    # packages=find_packages(where="cli", include=["cli", "cli.*"]),
    packages=find_packages(include=["cli", "cli.*"]),
    python_requires='>=3.11',
    install_requires=REQUIREMENTS,

    entry_points={
        'console_scripts': ['ai-ops-cli=cli.main:main']
    },
)
