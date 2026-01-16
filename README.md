# quickinventory
Python tools for inventree to speed up tasks such as adding parts.


## Setup
Run:
```
pip install -r requirements.txt
```
Then run using python.


## Errors

### ImportError: Unable to find dmtx shared library
You need to install libdmtx. You can install it from source [here](https://github.com/dmtx/libdmtx).
Very simply, you need to run:
```
git clone https://github.com/dmtx/libdmtx
cd libdmtx
./autogen.sh
./configure
make
sudo make install
```

### ImportError: Unable to find zbar shared library
Again, missing this lib.
If on macos, simply install with brew (`brew install zbar`
Run:
```
git clone https://github.com/mchehab/zbar
cd zbar
autoreconf -vfi
./configure --with-python=auto
make
```
