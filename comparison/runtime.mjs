import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import createModule from './runtime/interpreter_web.js';
export const ROOT = path.dirname(fileURLToPath(import.meta.url));
let runtimeErrors = [];
console.error = (...args) => {
  const line = args.join(' ');
  if (!line.startsWith('On condition:')) runtimeErrors.push(line);
};
const M = await createModule();
const stdlib = fs.readFileSync(path.join(ROOT,'./runtime/stdlib.sexp'),'utf8');

export class Autumn {
  constructor(source, seed=42) {
    runtimeErrors = [];
    this.it = new M.Interpreter();
    this.it.setVerbose(false);
    const status = this.it.runScript(source, stdlib, '', BigInt(seed));
    if (status !== 'Success') { this.it.delete(); throw Error(status); }
    this.check();
  }
  check() { if (runtimeErrors.length) throw Error(runtimeErrors.splice(0,3).join('; ')); }
  render() {
    const raw = JSON.parse(this.it.renderAll());
    this.check();
    const [w,h] = Array.isArray(raw.GRID_SIZE) ? raw.GRID_SIZE : [raw.GRID_SIZE,raw.GRID_SIZE];
    const bg = this.it.getBackground() || 'black';
    const grid=Array.from({length:h},()=>Array(w).fill(bg));
    const cells=[];
    for(const [key,value] of Object.entries(raw)) {
      if(key==='GRID_SIZE') continue;
      for(const cell of value) {
        const {x,y}=cell.position;
        if(Number.isInteger(x)&&Number.isInteger(y)&&x>=0&&y>=0&&x<w&&y<h) {grid[y][x]=cell.color;cells.push({x,y});}
      }
    }
    return {grid,w,h,bg,cells};
  }
  step(action) {
    if(action.type==='click') this.it.click(action.x,action.y);
    else if(['left','right','up','down'].includes(action.type)) this.it[action.type]();
    else if(action.type!=='noop') throw Error('Bad action '+JSON.stringify(action));
    this.it.step(); this.check(); return this.render();
  }
  close() { this.it.delete(); }
}

export function replay(source, actions, seed=42) {
  const env=new Autumn(source,seed);
  try { return [env.render(),...actions.map(a=>env.step(a))]; }
  finally {env.close();}
}
