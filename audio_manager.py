import logging
import multiprocessing
import time
import os
import pygame

# Set up logging for this module
logger = logging.getLogger("AudioManager")

class AudioManager:
    def __init__(self, audio_queue, audio_playing_flag, audio_dir="audio_cache"):
        self.audio_queue = audio_queue
        self.audio_playing_flag = audio_playing_flag
        self.audio_dir = audio_dir
        self.shutdown_flag = multiprocessing.Event()
        self.currently_playing = None # To track the state

    def start(self):
        try:
            pygame.mixer.init()
            logger.info("Pygame mixer initialized successfully in the audio process.")
        except Exception as e:
            logger.error(f"Failed to initialize pygame mixer in audio process: {e}")
            return

        logger.info("Audio Manager Process Started")
        while not self.shutdown_flag.is_set():
            # 1. Check for and handle incoming messages
            try:
                message = self.audio_queue.get_nowait() # Non-blocking get
                
                if message == "shutdown":
                    logger.info("Shutdown signal received.")
                    self.shutdown_flag.set()
                    continue

                logger.info(f"Received request: '{message}'")
                self.handle_request(message)

            except multiprocessing.queues.Empty:
                # No new messages, proceed to check status
                pass
            except Exception as e:
                logger.error(f"Error processing queue: {e}", exc_info=True)

            # 2. Check and update the status of the currently playing audio
            if self.currently_playing and not pygame.mixer.music.get_busy():
                logger.info(f"Finished playing '{self.currently_playing}'.")
                self.audio_playing_flag.clear()
                logger.info("AUDIO_FLAG: Cleared flag (audio finished naturally).")
                self.currently_playing = None
                logger.info("Resuming listening.")

            time.sleep(0.1) # Prevent busy-waiting
        
        pygame.mixer.quit()
        logger.info("Audio Manager Shutting Down")

    def handle_request(self, message):
        """Parses command messages and acts on them immediately."""
        if not isinstance(message, dict):
            logger.warning(f"Invalid message type received: {type(message)}")
            return

        command = message.get('command')

        try:
            if command == 'play':
                audio_file_name = message.get('file')
                if not audio_file_name:
                    logger.warning("Play command received without a file.")
                    return

                audio_file = os.path.join(self.audio_dir, audio_file_name)
                if os.path.exists(audio_file):
                    # Stop any previous sound and play the new one
                    pygame.mixer.music.stop()
                    
                    self.audio_playing_flag.set()
                    logger.info(f"AUDIO_FLAG: Set flag to True (playing: {audio_file_name}).")
                    self.currently_playing = audio_file_name
                    
                    logger.info(f"Playing '{audio_file}' and blocking listening.")
                    pygame.mixer.music.load(audio_file)
                    pygame.mixer.music.play()
                else:
                    logger.warning(f"Audio file not found '{audio_file}'")

            elif command == 'stop':
                if self.currently_playing:
                    logger.info(f"Stop command received. Halting '{self.currently_playing}'.")
                    pygame.mixer.music.stop()
                    self.audio_playing_flag.clear()
                    logger.info("AUDIO_FLAG: Cleared flag (stopped by command).")
                    self.currently_playing = None
                    logger.info("Audio stopped by command and listening resumed.")
            else:
                logger.warning(f"Unknown command in message: {message}")

        except Exception as e:
            logger.error(f"Error handling request '{message}': {e}", exc_info=True)
            # Reset state on error
            self.audio_playing_flag.clear()
            self.currently_playing = None
            logger.warning("Cleared audio state due to an error.")


def audio_manager_process(audio_queue, audio_playing_flag, shutdown_flag):
    """The target function for the multiprocessing.Process."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    audio_manager = AudioManager(audio_queue, audio_playing_flag)
    audio_manager.shutdown_flag = shutdown_flag
    audio_manager.start()

# The __main__ block is for independent testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Testing Audio Manager...")
    test_queue = multiprocessing.Queue()
    test_flag = multiprocessing.Event()
    test_shutdown = multiprocessing.Event()
    
    manager_process = multiprocessing.Process(target=audio_manager_process, args=(test_queue, test_flag, test_shutdown))
    manager_process.start()
    
    try:
        logger.info("Main Test: Sending play request for 'social_distance.mp3'.")
        test_queue.put({'command': 'play', 'file': 'social_distance.mp3'})
        
        time.sleep(1)
        if test_flag.is_set(): logger.info("Main Test: SUCCESS - Flag is set while playing.")
        else: logger.error("Main Test: FAILURE - Flag is not set while playing.")

        logger.info("Main Test: Sending 'stop' command to interrupt.")
        test_queue.put({'command': 'stop'})
        time.sleep(0.5)
        if not test_flag.is_set(): logger.info("Main Test: SUCCESS - Flag is cleared after stop command.")
        else: logger.error("Main Test: FAILURE - Flag is not cleared after stop command.")

        logger.info("Main Test: Sending another play request.")
        test_queue.put({'command': 'play', 'file': 'overcrowding.mp3'})
        time.sleep(3) # Let it finish
        if not test_flag.is_set(): logger.info("Main Test: SUCCESS - Flag is cleared automatically after finishing.")
        else: logger.error("Main Test: FAILURE - Flag is not cleared after finishing.")

    finally:
        logger.info("Main Test: Sending shutdown signal.")
        test_shutdown.set()
        manager_process.join(timeout=5)
        logger.info("Main Test: Audio Manager test complete.")

