

To create a windows exe:
install python2.7 32bit edition (not 64-bit)
install pygame 1.9.1 32bit edition
install py2exe2.7 32 bit edition
install pywin32 py2.7 edition
install setuptools for python 2.7
install NSIS installer?

download the pygame2exe.py script floating about on the internet, update the values
run the pygame2exe.py script which will create your dist directory
python pygame2exe.py 

will create a dist directory you can zip up.

OR you can create an installer:

python game2exe.py bdist --formats=wininst --bitmap=installer.bmp

installer.bmp is a 152x261 bitmap
