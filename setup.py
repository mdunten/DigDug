from setuptools import setup, find_packages

setup(
    name="digdug",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.28",
    ],
    entry_points={
        "console_scripts": [
            "digdug=digdug.cli:main",
        ],
    },
)
