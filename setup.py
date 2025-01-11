from setuptools import setup, find_packages

setup(
	name="freight_fate",
	version="0.1",
	packages=find_packages(),
	package_dir={'': 'src'},
	install_requires=[
		'pygame',
	],
)