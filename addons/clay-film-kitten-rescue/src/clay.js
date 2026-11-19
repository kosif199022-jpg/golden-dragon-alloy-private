// Soft clay material: MeshStandardMaterial + lumpy vertices, thumb-press normal noise and a soft rim (fake SSS).
import * as THREE from 'three';

const NOISE = /* glsl */ `
float hash3(vec3 p){ p = fract(p*0.3183099 + .1); p *= 17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float vnoise(vec3 x){
  vec3 i = floor(x); vec3 f = fract(x); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hash3(i+vec3(0,0,0)),hash3(i+vec3(1,0,0)),f.x), mix(hash3(i+vec3(0,1,0)),hash3(i+vec3(1,1,0)),f.x),f.y),
             mix(mix(hash3(i+vec3(0,0,1)),hash3(i+vec3(1,0,1)),f.x), mix(hash3(i+vec3(0,1,1)),hash3(i+vec3(1,1,1)),f.x),f.y), f.z);
}
float fbm(vec3 p){ return vnoise(p)*0.55 + vnoise(p*2.1)*0.3 + vnoise(p*4.3)*0.15; }
`;

const cache = new Map();

export function clay(color, opts = {}) {
  const { rough = 0.78, bump = 0.35, freq = 9.0, lump = 0.012, rim = 0.22, emissive = 0x000000, emissiveIntensity = 0 } = opts;
  const key = [color, rough, bump, freq, lump, rim, emissive, emissiveIntensity].join('|');
  if (cache.has(key)) return cache.get(key);
  const m = new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: 0, emissive, emissiveIntensity });
  const c = new THREE.Color(color);
  const rimCol = c.clone().lerp(new THREE.Color(0xffffff), 0.55);
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uBump = { value: bump };
    sh.uniforms.uFreq = { value: freq };
    sh.uniforms.uLump = { value: lump };
    sh.uniforms.uRim = { value: rim };
    sh.uniforms.uRimCol = { value: rimCol };
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vObj;\nuniform float uLump; uniform float uFreq;\n' + NOISE)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vObj = position;
        transformed += normal * (fbm(position * uFreq * 0.35) - 0.5) * uLump;`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vObj;\nuniform float uBump; uniform float uFreq; uniform float uRim; uniform vec3 uRimCol;\n' + NOISE)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        {
          vec3 q = vObj * uFreq; float e = 0.02;
          float n0 = fbm(q);
          vec3 g = vec3(fbm(q + vec3(e,0,0)) - n0, fbm(q + vec3(0,e,0)) - n0, fbm(q + vec3(0,0,e)) - n0) / e;
          normal = normalize(normal - uBump * 0.04 * (mat3(viewMatrix) * g));
        }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        {
          float fr = pow(1.0 - abs(dot(normalize(normal), normalize(vViewPosition))), 2.6);
          totalEmissiveRadiance += uRimCol * fr * uRim;
        }`);
  };
  m.customProgramCacheKey = () => 'clay' + key;
  cache.set(key, m);
  return m;
}

// Glossy bits (eyes, water) — still soft.
export function gloss(color, rough = 0.18) {
  return new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: 0 });
}

export function glow(color, intensity = 2.0) {
  return new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: intensity, roughness: 0.5 });
}
