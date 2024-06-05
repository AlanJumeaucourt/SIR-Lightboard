import os
import glob
import pickle
import keyboard
import discord
import asyncio
import logging
from typing import Optional, Tuple
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaFileUpload
import googleapiclient.errors
from obswebsocket import obsws, requests as obs_requests
from dotenv import load_dotenv
from tkinter import Tk, Label
import nest_asyncio
import threading
import queue
from keyboard import KeyboardEvent
import time
nest_asyncio.apply()

# Load environment variables from .env file
load_dotenv()

# Text variables for translation
TXT_LOG_FILE = 'lightboard.txt'
TXT_CONSOLE_HANDLER_LEVEL = logging.DEBUG
TXT_FILE_HANDLER_LEVEL = logging.DEBUG
TXT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
TXT_LOGGER_STARTING_APP = 'Starting Lightboard app...'
TXT_OBS_HOST = os.getenv("OBS_HOST", "localhost")
TXT_OBS_PORT = int(os.getenv("OBS_PORT", 4455))
TXT_OBS_VIDEO_PATH = os.getenv("OBS_VIDEO_PATH", r'/home/user/Videos')
TXT_OBS_CONNECTED = 'Connected to OBS at {host}:{port}'
TXT_OBS_FAILED_CONNECT = 'Failed to connect to OBS at {host}:{port}. Retrying in {delay} seconds...'
TXT_OBS_CONNECT_ERROR = 'Unable to connect to OBS at {host}:{port} after {retries * delay} seconds.'
TXT_OBS_START_RECORD = 'Started recording'
TXT_OBS_STOP_RECORD = 'Stopped recording'
TXT_OBS_DISCONNECTED = 'Disconnected from OBS'
TXT_OBS_LATEST_VIDEO = 'Latest video found: {video}'
TXT_YT_CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE", 'client_secret.json')
TXT_YT_TOKEN_FILE = os.getenv("TOKEN_FILE", 'token.pkl')
TXT_YT_SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
TXT_YT_CLIENT_INIT = 'YouTube client initialized'
TXT_YT_CREDENTIALS_LOADED = 'Loaded credentials from token file'
TXT_YT_TOKEN_NOT_FOUND = 'Token file not found, creating new credentials'
TXT_YT_CREDENTIALS_SAVED = 'New credentials saved to token file'
TXT_YT_UPLOAD_TITLE = 'Video TC INSA Lyon'
TXT_YT_UPLOAD_DESCRIPTION = ''
TXT_YT_UPLOAD_TAGS = ['tag1', 'tag2']
TXT_YT_VIDEO_URL = 'https://www.youtube.com/watch?v={video_id}'
TXT_YT_VIDEO_UPLOADED = 'Video uploaded to YouTube: {video_id}'
TXT_DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "1242449552850681958"))
TXT_DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
TXT_DISCORD_INIT = 'Discord notifier initialized'
TXT_DISCORD_MSG_SENT = 'Message sent to Discord channel {channel_id}'
TXT_DISCORD_CHANNEL_ERROR = 'The channel ID is incorrect, right-click the channel to get the ID'
TXT_DISCORD_MSG_TEMPLATE = "Votre vidéo est accessible grâce à l'URL suivant : \n{url}"
TXT_GUI_WAITING = 'EN ATTENTE'
TXT_GUI_IN_PROGRESS = 'EN COURS'
TXT_GUI_COMPLETED = 'TERMINÉ'
TXT_GUI_ERROR = 'ERROR'
TXT_GUI_GOOGLE_QUOTA_ERROR = 'Google quota exceeded'
TXT_GUI_UNEXPECTED_ERROR = 'An unexpected error occurred'

class Logger:
    """
    A custom logger class that sets up logging to both console and file.
    
    Attributes:
        logger (logging.Logger): The logger instance.
    """
    def __init__(self, name: str, log_file: str = TXT_LOG_FILE):
        """
        Initializes the Logger with a specific name and optional log file.
        
        Args:
            name (str): The name of the logger.
            log_file (str): The file to log messages to.
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Create console handler for logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(TXT_CONSOLE_HANDLER_LEVEL)

        # Create file handler for logging
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(TXT_FILE_HANDLER_LEVEL)

        # Create formatters and add them to handlers
        formatter = logging.Formatter(TXT_LOG_FORMAT)
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def get_logger(self):
        """
        Returns the logger instance.
        
        Returns:
            logging.Logger: The logger instance.
        """
        return self.logger


class OBSRecorder:
    """
    A class to manage OBS recording operations.

    Attributes:
        logger (logging.Logger): The logger instance.
        host (str): The OBS host.
        port (int): The OBS port.
        video_path (str): The path to save the recorded videos.
        client (obsws): The OBS WebSocket client.
    """
    def __init__(self, logger: logging.Logger):
        """
        Initializes the OBSRecorder with a logger instance.
        
        Args:
            logger (logging.Logger): The logger instance.
        """
        self.logger = logger
        self.host: str = TXT_OBS_HOST
        self.port: int = TXT_OBS_PORT
        self.video_path: str = TXT_OBS_VIDEO_PATH
        self.client = obsws(self.host, self.port)

        self.connect_with_retry()
        
    def connect_with_retry(self, retries: int = 30, delay: int = 1) -> None:
        """
        Attempts to connect to the OBS WebSocket server with retries.
        
        Args:
            retries (int): Number of retries before giving up.
            delay (int): Delay between retries in seconds.
        """
        connected = False
        for _ in range(retries):
            try:
                self.client.connect()
                connected = True
                break
            except Exception as e:
                self.logger.warning(TXT_OBS_FAILED_CONNECT.format(host=self.host, port=self.port, delay=delay))
                time.sleep(delay)
        
        if not connected:
            raise ConnectionError(TXT_OBS_CONNECT_ERROR.format(host=self.host, port=self.port, retries=retries, delay=delay))
        
        self.logger.info(TXT_OBS_CONNECTED.format(host=self.host, port=self.port))

    def start_recording(self) -> None:
        """
        Starts the OBS recording.
        """
        self.client.call(obs_requests.StartRecord())
        self.logger.info(TXT_OBS_START_RECORD)

    def stop_recording(self) -> None:
        """
        Stops the OBS recording.
        """
        self.client.call(obs_requests.StopRecord())
        self.logger.info(TXT_OBS_STOP_RECORD)

    def disconnect(self) -> None:
        """
        Disconnects the OBS WebSocket client.
        """
        self.client.disconnect()
        self.logger.info(TXT_OBS_DISCONNECTED)

    def find_latest_video(self) -> Optional[str]:
        """
        Finds the latest recorded video file.
        
        Returns:
            Optional[str]: The path to the latest video file, or None if no files are found.
        """
        video_files = glob.glob(os.path.join(self.video_path, '*.mkv'))
        if not video_files:
            return None
        latest_video = max(video_files, key=os.path.getmtime)
        self.logger.info(TXT_OBS_LATEST_VIDEO.format(video=latest_video))
        return latest_video


class YouTubeUploader:
    """
    A class to manage video uploads to YouTube.

    Attributes:
        SCOPES (list): The scopes required for the YouTube API.
        logger (logging.Logger): The logger instance.
        client_secrets_file (str): The path to the client secrets file.
        token_file (str): The path to the token file.
        credentials: The credentials for the YouTube API.
        youtube (Resource): The YouTube API client.
    """
    SCOPES = TXT_YT_SCOPES

    def __init__(self, logger: logging.Logger):
        """
        Initializes the YouTubeUploader with a logger instance.
        
        Args:
            logger (logging.Logger): The logger instance.
        """
        self.logger = logger
        self.client_secrets_file: str = TXT_YT_CLIENT_SECRETS_FILE
        self.token_file: str = TXT_YT_TOKEN_FILE
        self.credentials = self.get_credentials()
        self.youtube: Resource = build('youtube', 'v3', credentials=self.credentials)
        self.logger.info(TXT_YT_CLIENT_INIT)

    def get_credentials(self):
        """
        Retrieves the credentials for the YouTube API, loading them from a file or creating new ones if not found.
        
        Returns:
            Credentials: The credentials for the YouTube API.
        """
        try:
            with open(self.token_file, 'rb') as token:
                self.logger.info(TXT_YT_CREDENTIALS_LOADED)
                return pickle.load(token)
        except FileNotFoundError:
            self.logger.warning(TXT_YT_TOKEN_NOT_FOUND)
            flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, self.SCOPES)
            credentials = flow.run_local_server(port=0)
            with open(self.token_file, 'wb') as token:
                pickle.dump(credentials, token)
            self.logger.info(TXT_YT_CREDENTIALS_SAVED)
            return credentials

    def upload_video(self, video_file: str) -> str:
        """
        Uploads a video to YouTube.
        
        Args:
            video_file (str): The path to the video file.
        
        Returns:
            str: The video ID of the uploaded video.
        """
        body = {
            'snippet': {
                'title': TXT_YT_UPLOAD_TITLE,
                'description': TXT_YT_UPLOAD_DESCRIPTION,
                'tags': TXT_YT_UPLOAD_TAGS,
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': 'public'
            }
        }

        media_body = MediaFileUpload(video_file, chunksize=-1, resumable=True)
        request = self.youtube.videos().insert(part='snippet,status', body=body, media_body=media_body)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                self.logger.info(f"Uploaded {int(status.progress() * 100)}%.")

        self.logger.info(TXT_YT_VIDEO_UPLOADED.format(video_id=response['id']))
        return response['id']


class DiscordNotifier():
    """
    A class to manage sending notifications to a Discord channel.

    Attributes:
        logger (logging.Logger): The logger instance.
        channel_id (int): The ID of the Discord channel.
    """
    def __init__(self, logger: logging.Logger, channel_id: int):
        """
        Initializes the DiscordNotifier with a logger instance and channel ID.
        
        Args:
            logger (logging.Logger): The logger instance.
            channel_id (int): The ID of the Discord channel.
        """
        self.logger = logger
        self.channel_id = channel_id
        self.logger.info(TXT_DISCORD_INIT)

    async def on_ready(self):
        """
        Called when the Discord client is ready.
        """
        self.logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def send_message(self, message: str):
        """
        Sends a message to the configured Discord channel.
        
        Args:
            message (str): The message to send.
        """
        channel = self.get_channel(self.channel_id)
        if channel:
            await channel.send(message)
            self.logger.info(TXT_DISCORD_MSG_SENT.format(channel_id=self.channel_id))
        else:
            self.logger.error(TXT_DISCORD_CHANNEL_ERROR)


class LightboardApp:
    """
    The main application class for the Lightboard app.

    Attributes:
        logger (logging.Logger): The logger instance.
        obs_recorder (OBSRecorder): The OBS recorder instance.
        youtube_uploader (YouTubeUploader): The YouTube uploader instance.
        discord_notifier (DiscordNotifier): The Discord notifier instance.
    """
    def __init__(self):
        """
        Initializes the LightboardApp.
        """
        self.logger = Logger(__name__).get_logger()
        self.obs_recorder = OBSRecorder(self.logger)
        self.youtube_uploader = YouTubeUploader(self.logger)
        self.discord_notifier = DiscordNotifier(self.logger, TXT_DISCORD_CHANNEL_ID)

    def run(self):
        """
        Runs the main loop of the Lightboard app.
        """
        self.logger.info(TXT_LOGGER_STARTING_APP)

        # Set up GUI
        root = Tk()
        status_label = Label(root, text=TXT_GUI_WAITING, font=("Helvetica", 48))
        status_label.pack()

        def update_status(text):
            status_label.config(text=text)
            root.update_idletasks()

        def handle_key_event(event: KeyboardEvent):
            if event.name == "f9" and event.event_type == "down":
                threading.Thread(target=self.process_recording, args=(update_status,)).start()

        keyboard.hook(handle_key_event)
        root.mainloop()

    def process_recording(self, update_status):
        """
        Handles the recording process, updating the GUI and uploading the video.

        Args:
            update_status (function): Function to update the status label in the GUI.
        """
        try:
            update_status(TXT_GUI_IN_PROGRESS)
            self.obs_recorder.start_recording()
            time.sleep(5)  # Record for 5 seconds for example purposes
            self.obs_recorder.stop_recording()
            latest_video = self.obs_recorder.find_latest_video()
            if latest_video:
                video_id = self.youtube_uploader.upload_video(latest_video)
                discord_message = TXT_DISCORD_MSG_TEMPLATE.format(url=TXT_YT_VIDEO_URL.format(video_id=video_id))
                asyncio.run(self.discord_notifier.send_message(discord_message))
            update_status(TXT_GUI_COMPLETED)
        except googleapiclient.errors.HttpError as e:
            if e.resp.status in [403, 429]:
                update_status(TXT_GUI_GOOGLE_QUOTA_ERROR)
            else:
                update_status(TXT_GUI_ERROR)
            self.logger.exception("An error occurred during the recording process.")
        except Exception:
            update_status(TXT_GUI_UNEXPECTED_ERROR)
            self.logger.exception("An unexpected error occurred during the recording process.")
        finally:
            self.obs_recorder.disconnect()


if __name__ == "__main__":
    app = LightboardApp()
    app.run()
