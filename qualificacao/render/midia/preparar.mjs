// Mídias de esboço da qualificação, geradas localmente e sem custo:
// imagens em degradê, um clipe com o número do quadro gravado (confere velocidade e
// congelamento), música sintetizada e as fontes copiadas do pacote local.
// Uso: node midia/preparar.mjs <pasta> --narracao narracao.wav --palavras palavras.json --duracao 65
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { parseArgs } from 'node:util';

const require = createRequire(import.meta.url);
const FONTE_DO_CLIPE = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf';
export const FONTES = [
  ['@fontsource/inter', 'inter-latin-400-normal.woff2'], ['@fontsource/inter', 'inter-latin-600-normal.woff2'],
  ['@fontsource/inter', 'inter-latin-800-normal.woff2'], ['@fontsource/inter', 'inter-latin-900-normal.woff2'],
  ['@fontsource/inter', 'inter-latin-ext-400-normal.woff2'], ['@fontsource/inter', 'inter-latin-ext-800-normal.woff2'],
  ['@fontsource/jetbrains-mono', 'jetbrains-mono-latin-500-normal.woff2'], ['@fontsource/jetbrains-mono', 'jetbrains-mono-latin-800-normal.woff2'],
];

const ffmpeg = args => execFileSync('ffmpeg', ['-v', 'error', '-nostdin', '-y', ...args], { stdio: 'inherit' });

export function prepararMidia(pasta, { narracao, palavras, duracao }) {
  mkdirSync(join(pasta, 'fontes'), { recursive: true });
  for (const [pacote, arquivo] of FONTES) {
    copyFileSync(join(dirname(require.resolve(`${pacote}/package.json`)), 'files', arquivo), join(pasta, 'fontes', arquivo));
  }
  const imagens = [['imagem-1.png', '0x1D4ED8', '0x10B981', 'ESBOÇO 1'], ['imagem-2.png', '0x7C3AED', '0xF59E0B', 'ESBOÇO 2']];
  for (const [nome, c0, c1, rotulo] of imagens) {
    if (existsSync(join(pasta, nome))) continue;
    ffmpeg(['-f', 'lavfi', '-i', `gradients=s=2400x2400:c0=${c0}:c1=${c1}:x0=0:y0=0:x1=2400:y1=2400:d=1:seed=7,format=rgb24`,
            '-vf', ['drawbox=x=300:y=300:w=700:h=700:color=white@0.25:t=fill', 'drawbox=x=1300:y=1100:w=900:h=500:color=black@0.25:t=fill',
                    'drawgrid=w=200:h=200:t=2:c=white@0.15',
                    `drawtext=fontfile=${FONTE_DO_CLIPE}:text='${rotulo}':fontsize=180:fontcolor=white:x=(w-tw)/2:y=(h-th)/2`].join(','),
            '-frames:v', '1', join(pasta, nome)]);
  }
  if (!existsSync(join(pasta, 'clipe.webm'))) {
    // Todo quadro é chave (-g 1): a busca de qualquer quadro é exata e rápida, na prévia e na gravação.
    ffmpeg(['-f', 'lavfi', '-i', 'testsrc2=s=1280x720:r=30:d=8',
            '-vf', `scale=out_color_matrix=bt709:out_range=tv,drawtext=fontfile=${FONTE_DO_CLIPE}:text='%{eif\\:n\\:d\\:3}':fontsize=220:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=20:x=(w-tw)/2:y=(h-th)/2`,
            '-c:v', 'libvpx-vp9', '-g', '1', '-crf', '30', '-b:v', '0', '-deadline', 'good', '-cpu-used', '4', '-row-mt', '1',
            // Cor marcada: sem marcação, o Chrome e o compositor do Remotion supõem matrizes diferentes.
            '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
            join(pasta, 'clipe.webm')]);
  }
  // Quadros do clipe em JPEG: o motor HTML mostra o quadro exato de cada instante, sem depender
  // da busca do <video> (que não avisa quando o quadro pedido é o mesmo que já estava na tela).
  mkdirSync(join(pasta, 'clipe-quadros'), { recursive: true });
  if (!existsSync(join(pasta, 'clipe-quadros', '0000.jpg'))) {
    ffmpeg(['-i', join(pasta, 'clipe.webm'), '-q:v', '2', '-start_number', '0', join(pasta, 'clipe-quadros', '%04d.jpg')]);
  }
  // Música: acorde com tremolo lento e uma batida a cada meio segundo, normalizada a −16 LUFS
  // como a narração, para que os ganhos do envelope sejam relativos à voz.
  const musica = join(pasta, 'musica.wav');
  const expr = (d) => `(0.18*sin(2*PI*220*t)+0.13*sin(2*PI*${277.18 + d}*t)+0.11*sin(2*PI*329.63*t))*(0.6+0.4*sin(2*PI*0.25*t))+0.35*sin(2*PI*110*t)*exp(-9*mod(t,0.5))`;
  ffmpeg(['-f', 'lavfi', '-i', `aevalsrc=exprs='${expr(0)}|${expr(1.5)}':s=48000:c=stereo:d=${Math.ceil(duracao) + 1}`,
          '-af', 'loudnorm=I=-16:TP=-2:LRA=7', '-ar', '48000', '-c:a', 'pcm_s16le', musica]);
  // Narração em estéreo, mesmo nível nos dois canais: com mono, o Chrome copia o canal inteiro e o
  // FFmpeg (-ac 2) atenua 3 dB, e a voz muda de nível entre prévia e exportação no Remotion.
  ffmpeg(['-i', resolve(narracao), '-af', 'pan=stereo|c0=c0|c1=c0', '-ar', '48000', '-c:a', 'pcm_s16le', join(pasta, 'narracao.wav')]);
  writeFileSync(join(pasta, 'palavras.json'), readFileSync(palavras));
  return {
    imagens: imagens.map(i => i[0]), clipe: { arquivo: 'clipe.webm', quadros: 'clipe-quadros/', fps: 30, total: 240, duracao: 8 },
    narracao: 'narracao.wav', musica: 'musica.wav',
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { positionals, values } = parseArgs({ allowPositionals: true, options: {
    narracao: { type: 'string' }, palavras: { type: 'string' }, duracao: { type: 'string' } } });
  const midia = prepararMidia(positionals[0], { ...values, duracao: Number(values.duracao) });
  writeFileSync(join(positionals[0], 'midia.json'), JSON.stringify(midia, null, 1));
  console.log('mídias prontas em', positionals[0]);
}
