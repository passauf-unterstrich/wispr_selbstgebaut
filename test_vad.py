"""Isolierter Silero-VAD-Test (mit soundfile statt torchaudio)."""
import subprocess, tempfile, time, os, shutil, sys

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
DAUER  = 15

print("── Silero-VAD Isolationstest ──\n")

tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
wav_pfad = tmp.name
tmp.close()

print(f"🔴 Aufnahme läuft {DAUER}s.")
print("   Sprich drei kurze Sätze mit je 1-2s Pause dazwischen.\n")

befehl = [
    FFMPEG, "-f", "avfoundation", "-i", ":default",
    "-ar", "16000", "-ac", "1",
    "-flush_packets", "1", "-avioflags", "direct",
    "-t", str(DAUER), "-y", wav_pfad,
]
t0 = time.time()
subprocess.run(befehl, capture_output=True)
print(f"✓ Aufnahme fertig ({time.time()-t0:.1f}s)")
print(f"  WAV: {os.path.getsize(wav_pfad)} bytes\n")

# ── VAD-Analyse mit soundfile (umgeht torchaudio-Bug) ──
print("🔍 VAD-Analyse läuft...")
import soundfile as sf
import torch
from silero_vad import load_silero_vad, get_speech_timestamps

t0 = time.time()
modell = load_silero_vad()
print(f"✓ Modell geladen ({time.time()-t0:.2f}s)")

t0 = time.time()
audio_np, sr = sf.read(wav_pfad, dtype="float32")
audio = torch.from_numpy(audio_np)
segmente = get_speech_timestamps(
    audio, modell,
    sampling_rate=sr,
    min_silence_duration_ms=500,
    min_speech_duration_ms=250,
    return_seconds=True,
)
print(f"✓ Analyse fertig ({time.time()-t0:.2f}s, Sample-Rate {sr} Hz)\n")

# ── Ergebnis ──
print("── Sprech-Segmente ──")
if not segmente:
    print("⚠️  Keine Sprache erkannt.")
    sys.exit(1)
for i, seg in enumerate(segmente, 1):
    print(f"  Segment {i}: {seg['start']:5.2f}s → {seg['end']:5.2f}s   (Dauer {seg['end']-seg['start']:.2f}s)")

print("\n── Pausen zwischen Segmenten ──")
if len(segmente) < 2:
    print("  (Nur ein Segment – keine Pausen erkannt.)")
else:
    for i in range(len(segmente)-1):
        print(f"  Nach Segment {i+1}: {segmente[i+1]['start']-segmente[i]['end']:.2f}s Stille")

os.unlink(wav_pfad)
print("\n🎉 VAD funktioniert.")
