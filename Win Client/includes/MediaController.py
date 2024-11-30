import asyncio
import logging
from typing import Callable
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager
)
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionMediaProperties
from .enums.MediaAction import MediaAction

class MediaController:
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger
        self.sessions = None
        self.current_session = None

    async def initialize(self):
        self.logger.info("Initializing.")
        self.sessions = await MediaManager.request_async()
        self.current_session = self.sessions.get_current_session()

        if not self.current_session:
            if self.logger is not None:
                self.logger.warning("No active media session found.")
            return
        
        if self.logger is not None:
            self.logger.info("Media session initialized.")
        return


    async def _perform_action_async(self, action: MediaAction):
        if not self.current_session:
            if self.logger is not None:
                self.logger.warning("No active media session available.")
            return

        try:
            if action == MediaAction.PLAY:
                await self.current_session.try_play_async()
                if self.logger is not None:
                    self.logger.info("Track resumed.")
            elif action == MediaAction.PAUSE:
                await self.current_session.try_pause_async()
                if self.logger is not None:
                    self.logger.info("Track paused.")
            elif action == MediaAction.NEXT:
                await self.current_session.try_skip_next_async()
                if self.logger is not None:
                    self.logger.info("Skipped to next track.")
            elif action == MediaAction.PREVIOUS:
                await self.current_session.try_skip_previous_async()
                if self.logger is not None:
                    self.logger.info("Skipped to previous track.")
            elif action == MediaAction.NOW_PLAYING:
                return await self.get_now_playing()
            else:
                if log:
                    self.logger.error("Unknown action.")
        except Exception as e:
            if self.logger is not None:
                self.logger.error(f"Failed to perform action {action.name}: {e}")

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
            if self.logger is not None and not logger_force_disable:
                self.logger.warning("No active media session available.")
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

                if self.logger is not None and not logger_force_disable:
                    self.logger.debug(f"Successfully fetched now playing information: {result}")
                return result
            except Exception as e:
                if self.logger is not None and not logger_force_disable:
                    self.logger.error(f"Error fetching now playing information: {e}")
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