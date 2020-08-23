import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="singer-pathmatch",
    version="0.0.1",
    author="Angaza",
    description="select fields in a Singer catalog using git-style pattern matching",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/angaza/singer-patch-catalog",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "singer-pathmatch = singer_pathmatch.main:console_main",
        ]
    },
    python_requires='>=3.6',
)
