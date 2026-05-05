import os
from PIL import Image
import customtkinter as ctk
from config import ASSETS_DIR


_icon_cache = {}

def get_icon(filename, size=(20, 20), light_filename=None):
    """
    Fetches an image from the assets folder.
    Caches the result so disk I/O only happens once per icon/size combination.
    Dark mode: E3E3E3.
    Light mode: 333333.
    """
    cache_key = (filename, size, light_filename)

    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    dark_path = os.path.join(ASSETS_DIR, filename)

    light_path = os.path.join(ASSETS_DIR, light_filename) if light_filename else dark_path

    try:
        dark_img = Image.open(dark_path)
        light_img = Image.open(light_path)

        ctk_img = ctk.CTkImage(dark_image=dark_img, light_image=light_img, size=size)

        _icon_cache[cache_key] = ctk_img
        return ctk_img

    except FileNotFoundError as e:
        print(f"Warning: Icon file missing - {e}")
        return None


