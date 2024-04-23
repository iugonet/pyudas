import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="iugonet",
    version="0.1.0",
    author="IUGONET development team",
    author_email="iugonet-contact@iugonet.org",
    description="This is the IUGONET plugin tool for pySPEDAS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/iugonet/pyudas",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points = {
        'console_scripts': ['']
    },
    install_requires = [
        'pyspedas<1.5'
    ],
    python_requires='>=3.7',
)
