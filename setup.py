from setuptools import setup

setup(
    name='reload_win32',
    version='0.1',
    packages=['reload_win32'],
    url='https://github.com/iljau/reload_win32',
    license='',
    author='',
    author_email='',
    description='',
    entry_points = {
        'console_scripts': ['reload=reload_win32.reloader:main'],
    },
    install_requires=[
        'pywin32',
        'pathspec==0.5.5'
    ]
)
