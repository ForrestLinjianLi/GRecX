from setuptools import setup, find_packages

setup(
    name="grecx",
    python_requires='>3.5.0',
    version="0.0.2-dev",
    author="Desheng Cai",
    author_email="caidsml@gmail.com",
    packages=find_packages(
        exclude=[
            'benchmarks',
            'data',
            'demo',
            'dist',
            'doc',
            'docs',
            'logs',
            'models',
            'test'
        ]
    ),
    install_requires=[
        "tf_geometric >= 0.0.73"
    ],
    extras_require={

    },
    description="""
        A Fair Benchmark for GNN-based Recommendation.
    """,
    license="GNU General Public License v3.0 (See LICENSE)",
    long_description=open("README.rst", "r", encoding="utf-8").read(),
    url="https://github.com/maenzhier/GRecX"
)