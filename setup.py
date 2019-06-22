import setuptools

from pyvida import __version__


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyvida",
    version=__version__,
    author="Luke Miller",
    author_email="dodgyville@gmail.com",
    description="Cross platform point-and-click adventure game engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dodgyville/pyvida",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
