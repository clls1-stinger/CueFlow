import FFT from 'fft.js';
// Binary speech/text activity correlation. Text content and language are never compared.
export function align(speech, cues, { rate = 50, maxOffset = 300, fixFramerate = true } = {}, progress = () => {}) {
  const active = speech.reduce((a, b) => a + b, 0);
  if (active < rate || active > speech.length * 0.98) throw new Error('noSpeech');
  if (cues.length < 3) throw new Error('fewCues');
  const factors = fixFramerate ? [1, 25 / 24, 24 / 25, 25 / (24000 / 1001), (24000 / 1001) / 25, 1000 / 1001, 1001 / 1000] : [1];
  const extent = Math.max(speech.length, Math.ceil(cues.at(-1).end * rate * 1.06));
  let n = 1;
  while (n < extent * 2) n *= 2;
  const fft = new FFT(n);
  const input = new Float64Array(n); input.set(speech);
  const audioFFT = fft.createComplexArray(); fft.realTransform(audioFFT, input); fft.completeSpectrum(audioFFT);
  const subFFT = fft.createComplexArray(), product = fft.createComplexArray(), output = fft.createComplexArray();
  const limit = Math.floor(maxOffset * rate);
  let best = { score: -Infinity, offset: 0, scale: 1 };
  const evaluate = scale => {
    input.fill(0);
    for (const cue of cues) input.fill(1, Math.max(0, Math.round(cue.start * scale * rate)), Math.min(n, Math.round(cue.end * scale * rate)));
    let subActive = 0; for (let i = 0; i < extent; i++) subActive += input[i];
    const denom = Math.sqrt(active * (1 - active / extent) * subActive * (1 - subActive / extent));
    if (!denom) return;
    fft.realTransform(subFFT, input); fft.completeSpectrum(subFFT);
    for (let i = 0; i < product.length; i += 2) {
      product[i] = audioFFT[i] * subFFT[i] + audioFFT[i + 1] * subFFT[i + 1];
      product[i + 1] = audioFFT[i + 1] * subFFT[i] - audioFFT[i] * subFFT[i + 1];
    }
    fft.inverseTransform(output, product);
    for (let shift = -limit; shift <= limit; shift++) {
      const offset = shift / rate;
      if (cues[0].start * scale + offset < -0.5 || cues.at(-1).end * scale + offset > speech.length / rate + 5) continue;
      const value = output[2 * (shift < 0 ? n + shift : shift)];
      const score = (value - active * subActive / extent) / denom;
      if (score > best.score) best = { score, offset, scale };
    }
  };
  factors.forEach((scale, i) => { evaluate(scale); progress((i + 1) / (factors.length + (fixFramerate ? 6 : 0))); });
  // Refine small drift around the best standard frame-rate ratio, at decreasing steps.
  if (fixFramerate) for (const step of [0.0005, 0.00015, 0.00005]) {
    const center = best.scale;
    evaluate(center - step); evaluate(center + step);
    progress(0.85);
  }
  if (best.score < 0.12) throw new Error('weakMatch');
  if (Math.abs(best.offset) >= maxOffset - 0.02) throw new Error('offsetLimit');
  return best;
}
