# ReMeM-Video-Player
A desktop video player that remembers where you left off — and takes that memory with you, wherever the folder goes.

## The story behind this project

I wanted to keep a bunch of movies and shows on a USB drive and carry it between computers — my laptop at home, my work machine, a friend's PC, whatever was available. Every time I plugged the drive in somewhere new, I had to start each video from the beginning, or scribble down the timestamp on a sticky note like it was 2005.

I looked around for a video player that would just... remember. Not synced to a cloud account. Not tied to a specific machine's app data folder. Not storing "recently played" in some registry key that dies the moment I switch computers. I wanted something that would write its progress *into the folder itself*, so that when I picked up the drive and moved it somewhere else, the player on the new machine would just pick up where the old one stopped.

I couldn't find one. So I built one.

The rule is simple: **the progress file lives inside the video folder.** Copy the folder anywhere — another drive, a network share, a backup — and the resume information travels with it. No accounts, no cloud, no configuration. Just a folder that knows what you've watched.

---

## What it does

- **Plays almost any video format** by using VLC under the hood, so it gets all the codec support your system already has (plus everything VLC bundles).
- **Remembers position per file.** Close the app mid-movie, reopen it a week later on a different computer — it resumes exactly where you stopped.
- **Remembers your audio and subtitle choices per file.** If you always watch that anime with the Japanese audio and English subs, it will keep those selections on every future play.
- **Shows a playlist** of every video in the folder, each tagged with its progress percentage and a ✔ when finished.
- **Supports embedded and external subtitles** with a menu for picking tracks and loading a `.srt` / `.ass` / `.vtt` file.
- **Fullscreen mode**, keyboard shortcuts, and a clean dark interface.
- **Everything is portable.** The only file it writes is a plain-text `watch_progress.json` sitting alongside your videos.

---

## Requirements

- Python 3.9 or newer
- **VLC 3.x installed** on the machine (matching your Python architecture — both 32-bit or both 64-bit)
