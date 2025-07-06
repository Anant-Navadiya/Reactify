from setuptools import setup, find_packages

setup(
    name='Reactify',
    version='1.0.0',
    description='Converts html to react',
    author='Anant Navadiya',
    author_email='contact@anantnavadiya.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[],
    entry_points={
        'console_scripts': [
            'reactify=reactify.main:main',
        ],
    },
    license='MIT',
)
