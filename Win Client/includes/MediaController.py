import asyncio
import logging
from typing import Callable
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager
)

from .enums.MediaAction import MediaAction

from includes.classes.BetterLog import BetterLog

class MediaController(BetterLog):
    def __init__(self, logger: logging.Logger = None):
        super().__init__(logger)
        self.sessions = None
        self.current_session = None

    async def initialize(self):
        self.log_info("Initializing.")
        self.sessions = await MediaManager.request_async()
        self.current_session = self.sessions.get_current_session()

        if not self.current_session:
            self.log_warn("No active media session found.")
            return
        
        self.log_info("Media session initialized.")
        return


    async def _perform_action_async(self, action: MediaAction):
        if not self.current_session:
            self.log_warn("No active media session available.")
            return

        try:
            match action:
                case MediaAction.PLAY:
                    await self.current_session.try_play_async()
                    self.log_info("Track resumed.")
                case MediaAction.PAUSE:
                    await self.current_session.try_pause_async()
                    self.log_info("Track paused.")
                case MediaAction.NEXT:
                    await self.current_session.try_skip_next_async()
                    self.log_info("Skipped to next track.")
                case MediaAction.PREVIOUS:
                    await self.current_session.try_skip_previous_async()
                    self.log_info("Skipped to previous track.")
                case MediaAction.NOW_PLAYING:
                    return await self.get_now_playing()
                case _:
                    self.log_error("Unknown action.")
                
        except Exception as e:
            self.log_error(f"Failed to perform action {action.name}: {e}")

    async def _perform_action(self, action: MediaAction):
        # asyncio.run(self._perform_action_async(action))
        return await self._perform_action_async(action)

    async def play(self):
        await self._perform_action(MediaAction.PLAY)

    async def pause(self):
        await self._perform_action(MediaAction.PAUSE,)

    async def next_track(self):
        await self._perform_action(MediaAction.NEXT)

    async def previous_track(self):
        await self._perform_action(MediaAction.PREVIOUS)

    async def get_now_playing(self, logger_force_disable=False):
        """
        Get Current audio information
        :return: dict or None
        """
        if not self.current_session:
            if not logger_force_disable:
                self.log_warn("No active media session available.")
            return None

        async def fetch_media_properties():
            try:
                properties = await self.current_session.try_get_media_properties_async()
                result = {
                    "title": properties.title,
                    "artist": properties.artist,
                    "album": properties.album_title,
                    "track_number": properties.track_number,
                }

                if not logger_force_disable:
                    self.log_debug(f"Successfully fetched now playing information: {result}")
                return result
            except Exception as e:
                if not logger_force_disable:
                    self.log_debug(f"Error fetching now playing information: {e}")
                return None

        return await fetch_media_properties()

    async def on_np_update(self, callback:Callable):
        async def get_np():
            return await self.get_now_playing(logger_force_disable=True)
        
        media_info = await get_np()
        while True:
            temp = await get_np()
            if temp != media_info:
                callback(temp)
                # self.logger.warning(f"INFO IS DIFFERENT: {temp}")
                media_info = temp




async def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    mc = MediaController(logger)
    await mc.initialize()
    await mc.get_now_playing()
    await mc.play()

if __name__ == "__main__":    
    asyncio.run(main())