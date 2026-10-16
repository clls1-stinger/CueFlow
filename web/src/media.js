import { MAX_DURATION } from './subtitles.js';
export class MediaSession {
  constructor(report) { this.report = report; this.abort = new AbortController(); this.stopped = false; }
  async open(file) {
    if (file.size > 2 * 1024 ** 3) throw new Error('tooLarge');
    this.report('loading', 0);
    const { FFmpeg } = await import(/* @vite-ignore */ '/engine/ffmpeg/index.js');
    if (this.stopped) throw new Error('cancelled');
    this.ff = new FFmpeg();
    const res = await fetch('/engine/manifest.json', { signal: this.abort.signal });
    if (!res.ok) throw new Error('engineLoad');
    const manifest = await res.json(), chunks = [];
    for (const [i, chunk] of manifest.chunks.entries()) {
      const r = await fetch(`/engine/${chunk.name}`, { signal: this.abort.signal });
      if (!r.ok) throw new Error('engineLoad');
      const data = await r.arrayBuffer();
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', data)), x => x.toString(16).padStart(2, '0')).join('');
      if (data.byteLength !== chunk.bytes || hash !== chunk.sha256) throw new Error('engineLoad');
      chunks.push(data); this.report('loading', (i + 1) / manifest.chunks.length);
    }
    const url = URL.createObjectURL(new Blob(chunks, { type: 'application/wasm' }));
    try { await this.ff.load({ coreURL: new URL('/engine/ffmpeg-core.js', location.href).href, wasmURL: url }); }
    finally { URL.revokeObjectURL(url); }
    if (this.stopped) throw new Error('cancelled');
    await this.ff.createDir('/input');
    // WORKERFS reads the selected File on demand; never copy a whole film to MEMFS.
    const safeFile = new File([file], 'media', { type: file.type });
    if (!await this.ff.mount('WORKERFS', { files: [safeFile] }, '/input')) throw new Error('mountFailed');
    this.report('probing', 0);
    await this.ff.ffprobe(['-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index,codec_name,channels:stream_tags=language,title:format=duration', '-of', 'json', '-o', 'probe.json', '/input/media'], 30000);
    // core 0.12.10 leaves ffprobe's return status at -1 even on success.
    // Validate its completed JSON output instead of trusting that status.
    let info;
    try { info = JSON.parse(await this.ff.readFile('probe.json', 'utf8')); }
    catch { throw new Error('mediaRead'); }
    this.duration = Number(info.format?.duration);
    if (!Number.isFinite(this.duration) || this.duration <= 0 || this.duration > MAX_DURATION) throw new Error('durationLimit');
    if (!info.streams?.length) throw new Error('noAudio');
    this.tracks = info.streams;
    return info.streams;
  }
  async extract(track) {
    if (!Number.isInteger(track) || track < 0 || track >= this.tracks.length) throw new Error('noAudio');
    this.report('extracting', 0);
    this.ff.on('progress', ({ time }) => this.report('extracting', Math.min(1, time / 1e6 / this.duration)));
    const code = await this.ff.exec(['-v', 'error', '-i', '/input/media', '-map', `0:a:${track}`, '-vn', '-sn', '-dn', '-ac', '1', '-ar', '8000', '-c:a', 'pcm_s16le', '-f', 's16le', '-y', 'audio.pcm'], 10 * 60 * 1000);
    if (code !== 0) throw new Error('mediaRead');
    const pcm = await this.ff.readFile('audio.pcm');
    this.ff.terminate(); this.ff = null;
    return pcm;
  }
  stop() { this.stopped = true; this.abort.abort(); this.ff?.terminate(); this.ff = null; }
}
