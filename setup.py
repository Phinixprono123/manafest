from setuptools import setup, find_packages

setup(
    name="manafest",
    version="0.1.0",
    description="Manafest: multi-backend package manager",
    author="Alkama Sudad",
    packages=find_packages(),  # will find manafest + subpackages
    install_requires=["rich", "psutil", "pygit2", "requests"],
    entry_points={
        "console_scripts": [
            "manafest=manafest.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
