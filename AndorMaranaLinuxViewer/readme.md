These two scripts are taking care of displaying images from Andor Marana camera in real time. We created this because Andor Solis is currently not supported on Linux.


Use it by running `GrabGUI.py`. Configuration is written in the self-explanatory `config.toml`.


This display script can be straightforwardly adapted to other cameras by modifying `GrabThread.py` which interfaces the camera SDK to the GUI module.


Note that we did not implemented all features, just what we needed.
