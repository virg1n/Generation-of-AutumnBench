import fs from 'node:fs';
import path from 'node:path';
import {Autumn} from './runtime.mjs';
const folder=path.resolve(process.argv[2]);
const cert=JSON.parse(fs.readFileSync(path.join(folder,'validation.json'),'utf8'));
const env=new Autumn(fs.readFileSync(path.join(folder,'world.sexp'),'utf8'));
try {
 const frames=[env.render().grid,...cert.actions.map(a=>env.step(a).grid)];
 if(JSON.stringify(frames)!==JSON.stringify(cert.frames))throw Error('Autumn/Python frame mismatch');
 console.log(JSON.stringify({valid:true,frames:frames.length}));
}finally{env.close();}
