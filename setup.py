from setuptools import find_packages, setup

packages = find_packages()
print(packages)
setup(
    name='quant_lib',
    version='1.0',
    packages=packages,
)