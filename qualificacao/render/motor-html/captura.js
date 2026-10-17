// Grava o que a prévia realmente toca: repassa o áudio e manda blocos ao documento,
// marcados com o quadro do contexto em que começam (para saber a que instante t pertencem).
class Captura extends AudioWorkletProcessor {
  constructor() { super(); this.l = []; this.r = []; this.inicio = null; }
  process(inputs, outputs) {
    const entrada = inputs[0], saida = outputs[0];
    if (!entrada.length) return true;
    for (let c = 0; c < saida.length; c++) saida[c].set(entrada[Math.min(c, entrada.length - 1)]);
    if (this.inicio === null) this.inicio = currentFrame;
    this.l.push(entrada[0].slice());
    this.r.push((entrada[1] ?? entrada[0]).slice());
    if (this.l.length === 32) {
      const juntar = partes => { const o = new Float32Array(partes.length * 128); partes.forEach((p, i) => o.set(p, i * 128)); return o; };
      this.port.postMessage({ quadro: this.inicio, l: juntar(this.l), r: juntar(this.r) });
      this.l = []; this.r = []; this.inicio = null;
    }
    return true;
  }
}
registerProcessor('captura', Captura);
