# ShortVideoCLI

ShortVideoCLI is an AI-assisted workflow for discovering compelling
moments in long-form videos and preparing them for short-form platforms.

The initial focus is gameplay footage, but the architecture is intended
to support other video genres.

## Planned workflow

1. Investigate a video and its available public information.
2. Optionally analyze authorized YouTube Analytics data.
3. Optionally inspect selected video frames.
4. Detect and rank potentially engaging moments.
5. Prepare candidates for human review.
6. Export approved clips using platform-specific presets.

## Supported platforms

- YouTube Shorts
- TikTok
- Instagram Reels

## Requirements

- Python 3.11+
- uv

## Installation

```bash
uv sync