from setuptools import setup
from pathlib import Path
from ai_ops_cli import VERSION

CON = {}
DIR = Path(__file__).parent
with open(str(DIR / 'requirements-cli.txt'), 'r') as fp:
    lines = fp.read().splitlines()
    CON['requirements-cli'] = lines if lines else []

setup(
    name='ai-ops-cli',
    version=VERSION,
    author='@antoninoLorenzo',
    url='https://github.com/antoninoLorenzo/AI-OPS',
    install_requires=CON['requirements-cli'],
    py_modules=['ai_ops_cli'],
    entry_points={
        'console_scripts': ['ai_ops_cli=ai_ops_cli:main']
    },
)
