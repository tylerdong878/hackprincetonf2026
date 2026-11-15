"""Grain of Salt over iMessage (Photon 2.0).

The bot is a thin client of the game API: `engine.Engine` turns a text from one phone into replies by calling
the same /api routes the web app uses, and `photon_io.PhotonIO` moves those texts and images over Photon.

Run:  uv run python -m backend.imessage        (the game server must be running on GOS_API_URL)
"""
