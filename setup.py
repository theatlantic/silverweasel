from setuptools import setup, find_packages
import silverweasel

setup(
    name="silverweasel",
    version=silverweasel.__version__,
    description="Silverweasel is a library for dealing with the IBM Silverpop API",
    author="Brian Muller",
    author_email="bamuller@gmail.com",
    license="MIT",
    url="http://github.com/theatlantic/silverweasel",
    packages=find_packages(),
    package_data={'': ['data/*.xsd']},
    python_requires='>=3',
    install_requires=["zeep==2.4.0","arrow==0.12.0","paramiko==2.4.0"]
)
