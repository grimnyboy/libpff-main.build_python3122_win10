install visual studio 2022
C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
cd C:\libpff-main
python prepare_windows_build.py
python setup.py build_ext --inplace
pip install .
