#! /usr/bin/env python


import setuptools

setuptools.setup(
    name="dclaw",
    version=versioneer.get_version(),
    author="",
    author_email="",
    description="",
    long_description="",
    long_description_content_type="text/markdown",
    url="",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=open("requirements.txt", "r").read().splitlines(),
)
