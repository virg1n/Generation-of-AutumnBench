import fs from 'node:fs';
import {measure} from './probe_metrics.mjs';
const jobs=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const rows=[];
for(const job of jobs){
 const source=fs.readFileSync(job.path,'utf8');
 rows.push({name:job.name,features:measure(source).features});
}
process.stdout.write(JSON.stringify(rows));
