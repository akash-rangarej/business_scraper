"""
registry.py

THIS is the dictionary your instructor described:
    key   = website name (as typed on the CLI)
    value = the plugin responsible for that website

To add a new website later (e.g. Yelp), you write a YelpPlugin(BasePlugin)
and add one line here -- nothing else in the codebase changes.
"""

from .google_plugin import GooglePlugin
from .facebook_plugin import FacebookPlugin

PLUGINS = {
    "google": GooglePlugin(),
    "facebook": FacebookPlugin(),
}
