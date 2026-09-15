"""
registry.py

THIS is the dictionary your instructor described:
    key   = website name (as typed on the CLI)
    value = the plugin responsible for that website

To add a new website later, you write a NewSitePlugin(BasePlugin)
and add one line here -- nothing else in the codebase changes.
"""

from .google_plugin import GooglePlugin
from .justdial_plugin import JustdialPlugin
from .sulekha_plugin import SulekhaPlugin

PLUGINS = {
    "google": GooglePlugin(),
    "justdial": JustdialPlugin(),
    "sulekha": SulekhaPlugin(),
}