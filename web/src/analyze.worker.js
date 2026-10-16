import { align } from './alignment.js';
self.onmessage = async ({ data }) => {
  try {
    const { default: builder } = await import(/* @vite-ignore */ '/engine/vad/vad.js');
    const response = await fetch('/engine/vad/libfvad.wasm');
    if (!response.ok) throw new Error('engineLoad');
    const VAD = await builder(await response.arrayBuffer());
    const vad = new VAD(2, 8000);
    const pcm = new Int16Array(data.pcm), frame = new Int16Array(160);
    const speech = new Float32Array(Math.floor(pcm.length / 160));
    try {
      for (let i = 0; i < speech.length; i++) {
        frame.set(pcm.subarray(i * 160, i * 160 + 160));
        const result = vad.processFrame(frame);
        if (result < 0) throw new Error('noSpeech');
        speech[i] = result;
        if (i % 10000 === 0) self.postMessage({ type: 'progress', phase: 'speech', value: i / speech.length });
      }
    } finally { vad.destroy(); }
    self.postMessage({ type: 'progress', phase: 'align', value: 0 });
    const result = align(speech, data.cues, data.options, value => self.postMessage({ type: 'progress', phase: 'align', value }));
    self.postMessage({ type: 'done', result, duration: pcm.length / 8000 });
  } catch (error) { self.postMessage({ type: 'error', error: error.message || String(error) }); }
};
