// Virtual microphone: the caller's Telugu WAV (window.__CALLER_B64) is played into the stream
// getUserMedia returns, so the app's own MediaRecorder -> WAV -> /api/call code runs unchanged.
navigator.mediaDevices.getUserMedia = async () => {
  const ctx = new AudioContext({sampleRate: 48000});
  const bin = Uint8Array.from(atob(window.__CALLER_B64), c => c.charCodeAt(0));
  const buf = await ctx.decodeAudioData(bin.buffer);
  const src = ctx.createBufferSource(); src.buffer = buf;
  const dest = ctx.createMediaStreamDestination(); src.connect(dest);
  setTimeout(() => src.start(), 150);
  return dest.stream;
};
