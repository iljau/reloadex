from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as f:
    readme = f.read()

packages = find_packages("src")
print("packages", packages)

setup(
    name='reloadex',
    version='0.6',
    url='https://github.com/iljau/reloadex',
    license='MIT',
    author='Ilja Umov',
    author_email='',
    description='Restart WSGI server on code changes',

    long_description=readme,
    long_description_content_type='text/markdown',

    packages=packages,
    package_dir={"": "src"},

    entry_points = {
        'console_scripts': [
            'reloadex=reloadex.reloader:main',
        ],
    },
    install_requires=[
        'pywin32;platform_system=="Windows"',
        'pathspec>=0.5.9'
    ],

    extras_require={
        'dev': [
            'flask',
            'uwsgi',
            'waitress',
        ]
    },

    keywords='reload wsgi',
    # https://pypi.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        # 'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
    ],
)
