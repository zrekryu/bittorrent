# bittorrent
Development in progress.

# Example
```py
import asyncio

from bittorrent import TorrentClient, TorrentSettings

async def main() -> None:
    torrent_settings: TorrentSettings = TorrentSettings(
        download_path=".",
        debug=True,
        desired_successful_trackers=1,
        tracker_http_timeout=5,
        tracker_udp_timeout=5,
        tracker_udp_retries=0
        )
    torrent_client: TorrentClient = await TorrentClient.initialize(
        torrent_file_path="<torrent-file-path>",  # Replace with your torrent file path.
        torrent_settings=torrent_settings
        )
    await torrent_client.start_leeching()
    await torrent_client.wait_until_download_complete()  # Nothing is actually downloaded as of now.
    await torrent_client.close()

asyncio.run(main())
```
