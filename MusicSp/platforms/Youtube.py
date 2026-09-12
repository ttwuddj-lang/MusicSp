import asyncio
import os
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist

DOWNLOAD_DIR = "downloads"


def time_to_seconds(time):
    stringt = str(time)
    return sum(
        int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":")))
    )


def _video_id(link: str) -> str:
    if not link:
        return ""
    if "v=" in link:
        return link.split("v=", 1)[1].split("&", 1)[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/", 1)[1].split("?", 1)[0].split("&", 1)[0]
    return link.rstrip("/").split("/")[-1].split("?", 1)[0]


async def _download_with_ytdlp(link: str, video: bool = False) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    vid = _video_id(link)
    if not vid:
        return None

    ext = "mp4" if video else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    if video:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": os.path.join(DOWNLOAD_DIR, f"{vid}.%(ext)s"),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }
    else:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": os.path.join(DOWNLOAD_DIR, f"{vid}.%(ext)s"),
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

    try:
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])

        await asyncio.to_thread(_download)

        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path

        # yt-dlp can choose a slightly different final extension/name.
        for name in os.listdir(DOWNLOAD_DIR):
            if name.startswith(f"{vid}.") and os.path.isfile(
                os.path.join(DOWNLOAD_DIR, name)
            ):
                candidate = os.path.join(DOWNLOAD_DIR, name)
                if os.path.getsize(candidate) > 0:
                    return candidate

        return None
    except Exception:
        for name in os.listdir(DOWNLOAD_DIR):
            if name.startswith(f"{vid}."):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, name))
                except Exception:
                    pass
        return None


async def download_song(link: str) -> str:
    return await _download_with_ytdlp(link, video=False)


async def download_video(link: str) -> str:
    return await _download_with_ytdlp(link, video=True)


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[
                            entity.offset : entity.offset + entity.length
                        ]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        res = await results.next()

        if not res or not res.get("result"):
            return "", "0:00", 0, "", ""

        for result in res["result"]:
            title = result.get("title", "")
            duration_min = result.get("duration", "0:00")
            thumbnails = result.get("thumbnails", [])
            thumbnail = (
                thumbnails[0]["url"].split("?")[0] if thumbnails else ""
            )
            vidid = result.get("id", "")
            duration_sec = (
                int(time_to_seconds(duration_min)) if duration_min else 0
            )

        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        res = await results.next()

        if res and res.get("result"):
            for result in res["result"]:
                return result.get("title", "")
        return ""

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        res = await results.next()

        if res and res.get("result"):
            for result in res["result"]:
                return result.get("duration", "0:00")
        return "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        res = await results.next()

        if res and res.get("result"):
            for result in res["result"]:
                thumbnails = result.get("thumbnails", [])
                return (
                    thumbnails[0]["url"].split("?")[0]
                    if thumbnails
                    else ""
                )
        return ""

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(
        self,
        link,
        limit,
        user_id,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]

        try:
            plist = await Playlist.get(link)
        except Exception:
            return []

        videos = plist.get("videos") or []
        ids = []

        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)

        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        res = await results.next()

        if not res or not res.get("result"):
            return {}, ""

        for result in res["result"]:
            title = result.get("title", "")
            duration_min = result.get("duration", "0:00")
            vidid = result.get("id", "")
            yturl = result.get("link", "")
            thumbnails = result.get("thumbnails", [])
            thumbnail = (
                thumbnails[0]["url"].split("?")[0] if thumbnails else ""
            )

        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }

        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        ytdl_opts = {"quiet": True, "no_warnings": True}

        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)

            for fmt in r.get("formats", []):
                try:
                    if "dash" not in str(fmt["format"]).lower():
                        formats_available.append(
                            {
                                "format": fmt["format"],
                                "filesize": fmt.get("filesize"),
                                "format_id": fmt["format_id"],
                                "ext": fmt["ext"],
                                "format_note": fmt.get("format_note"),
                                "yturl": link,
                            }
                        )
                except Exception:
                    continue

        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        a = VideosSearch(link, limit=10)
        res = await a.next()
        result = res.get("result") if res else []

        if not result or query_type >= len(result):
            return "", "0:00", "", ""

        title = result[query_type].get("title", "")
        duration_min = result[query_type].get("duration", "0:00")
        vidid = result[query_type].get("id", "")
        thumbnails = result[query_type].get("thumbnails", [])
        thumbnail = (
            thumbnails[0]["url"].split("?")[0] if thumbnails else ""
        )

        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link

        try:
            if video:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)

            if downloaded_file:
                return downloaded_file, True

            return None, False
        except Exception:
            return None, False


YouTube = YouTubeAPI()
