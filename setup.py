from setuptools import setup, find_packages

setup(
    name='subadjust',
    version='1.0.0',
    description='字幕时间轴批量校正工具 - 支持 SRT/ASS/VTT 格式',
    author='SubAdjust',
    packages=find_packages(),
    install_requires=[
        'chardet>=5.0.0',
    ],
    entry_points={
        'console_scripts': [
            'subadjust=subadjust.cli:main',
        ],
    },
    python_requires='>=3.8',
)
