import io
import pathlib
import re
import setuptools


# version load courtesy:
# https://stackoverflow.com/questions/17583443/what-is-the-correct-way-to-share-package-version-with-setup-py-and-the-package
here = pathlib.Path(__file__).parent
__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',  # It excludes inline comment too
    io.open(here / 'pyvida' / '__init__.py', encoding='utf_8_sig').read()
    ).group(1)


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyvida",
    version=__version__,
    author="Luke Miller",
    author_email="dodgyville@gmail.com",
    description="Cross platform point-and-click 2D adventure game engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dodgyville/pyvida",
    packages=setuptools.find_packages(),
    install_requires=[
        "euclid3",
        "pyglet",
        "babel",
        "fonttools",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
