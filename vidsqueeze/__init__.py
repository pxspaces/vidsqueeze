"""VidSqueeze: make video, audio and image files smaller, on any computer."""

#: The one place the version is written down.
#:
#: It used to be written in two places, here and in cli.py, and they drifted:
#: the command line reported a new version while the interface and the update
#: check still reported the old one, so the program told the user it was up to
#: date when it was not. Everything now reads this.
__version__ = "1.13.0"
