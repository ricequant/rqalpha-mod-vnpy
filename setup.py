from pip.req import parse_requirements

from setuptools import (
    find_packages,
    setup,
)

setup(
    name='rqalpha-mod-vnpy',
    version="0.9.6",
    description='A mod for RQAlpha to connect weith VN.PY',
    packages=find_packages(exclude=[]),
    author='Cuizi7',
    author_email='cuizi7@163.com',
    license='Apache License v2',
    package_data={'': ['*.*']},
    url='https://github.com/ricequant/rqalpha-mod-vnpy',
    install_requires=[str(ir.req) for ir in parse_requirements("requirements.txt", session=False)],
    zip_safe=False,
    classifiers=[
        'Programming Language :: Python',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: Unix',
        'Programming Language :: Python :: 2.7',
    ],
)