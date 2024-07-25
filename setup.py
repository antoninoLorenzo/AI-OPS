from setuptools import setup


setup(
    name='ai-ops-cli',
    version='0.0',
    author='Antonino Lorenzo',
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