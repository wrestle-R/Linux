# Local Whisper (`small.en`) Usage Guide

This setup uses `whisper.cpp` locally with `ggml-small.en.bin` in English mode.

## Files

- Setup script: `~/.config/quickshell/ii/scripts/speaking/ensure-whisper.sh`
- Transcribe script: `~/.config/quickshell/ii/scripts/speaking/transcribe.sh`
- Session script: `~/.config/quickshell/ii/scripts/speaking/record-session.sh`
- Groq cleanup script: `~/.config/quickshell/ii/scripts/speaking/groq-cleanup.sh`
- Model directory: `~/.local/share/quickshell-speaking/models/`
- History file: `~/.local/state/quickshell-speaking/history.json`

## 1. Ensure Runtime And Model

```bash
~/.config/quickshell/ii/scripts/speaking/ensure-whisper.sh
```

This builds or fetches `whisper.cpp` if needed and keeps only:

- `ggml-small.en.bin`

## 2. Transcribe One Audio File Locally

```bash
~/.config/quickshell/ii/scripts/speaking/transcribe.sh /path/to/audio-file.ogg
```

The script uses `ffmpeg` to convert the input to 16 kHz mono WAV before passing it to `whisper-cli`.

## 3. Use Clean Or Raw Session Mode

Clean mode uses local Whisper first, then Groq punctuation/capitalization cleanup:

```bash
SPEAKING_CLEANUP_MODE=groq ~/.config/quickshell/ii/scripts/speaking/record-session.sh sample /path/to/audio.ogg /tmp/speaking-clean
```

Raw mode uses local Whisper only and never calls Groq:

```bash
SPEAKING_CLEANUP_MODE=raw ~/.config/quickshell/ii/scripts/speaking/record-session.sh sample /path/to/audio.ogg /tmp/speaking-raw
```

Both modes write:

- Raw transcript: `<session-dir>/raw-transcript.txt`
- Final transcript: `<session-dir>/transcript.txt`
- History entry: `~/.local/state/quickshell-speaking/history.json`

## 4. Reuse In Other Projects

```bash
WHISPER_HELPER="$HOME/.config/quickshell/ii/scripts/speaking/transcribe.sh"
"$WHISPER_HELPER" ./sample.wav > transcript.txt
```

Optional cleanup:

```bash
cat transcript.txt | ~/.config/quickshell/ii/scripts/speaking/groq-cleanup.sh > cleaned.txt
```

If the Groq API call fails, the cleanup script returns the raw text.
