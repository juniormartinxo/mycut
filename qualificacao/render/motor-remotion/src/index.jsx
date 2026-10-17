import React from 'react';
import { Composition, registerRoot } from 'remotion';
import { Cena } from './Cena.jsx';

function Raiz() {
  return (
    <Composition id="Cena" component={Cena} fps={30} width={1080} height={1920} durationInFrames={1}
      defaultProps={{ cena: null, baseDaMidia: null }}
      calculateMetadata={({ props }) => ({
        width: props.cena.formato.largura, height: props.cena.formato.altura,
        durationInFrames: Math.round(props.cena.duracao * props.cena.formato.fps),
      })} />
  );
}

registerRoot(Raiz);
