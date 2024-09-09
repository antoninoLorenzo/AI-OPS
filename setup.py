from setuptools import setup

from ai_ops_cli import VERSION


setup(
    name='ai-ops-cli',
    version=VERSION,
    author='@antoninoLorenzo',
    requires=[
        'requests', 
        'rich'
    ],
    py_modules=['ai_ops_cli'],
    entry_points='''
        [console_scripts]
        ai-ops-cli=ai_ops_cli:main
    ''',
)