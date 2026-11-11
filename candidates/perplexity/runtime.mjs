export const VERSION = 1;
const clone = x => JSON.parse(JSON.stringify(x));
export function seed() {
 return {version:1, root:'purpose', focus:'purpose', nextId:5, nodes:{
 purpose:{id:'purpose',title:'What is it for?',body:'Give an intention a place. Explore a branch, or grow your own.',kind:'map',children:['notice','practice','build']},
 notice:{id:'notice',title:'Notice',body:'What deserves your attention? Add a place for it.',kind:'note',children:[]},
 practice:{id:'practice',title:'Practice',body:'Return to an action. Each repetition is saved with this garden.',kind:'counter',value:0,children:[]},
 build:{id:'build',title:'Build a place',body:'Create a nested map here. It uses the same runtime as this one.',kind:'map',children:[]}
 }};
}
export function validate(input) {
 if (!input || input.version!==VERSION || !input.nodes || typeof input.nodes!=='object' || Array.isArray(input.nodes)) throw Error('Unsupported garden format.');
 const keys=Object.keys(input.nodes); if (!keys.length || keys.length>2000) throw Error('A garden must contain 1–2000 places.');
 const own=k=>Object.prototype.hasOwnProperty.call(input.nodes,k);
 if(!own(input.root)||!own(input.focus)||!Number.isSafeInteger(input.nextId)||input.nextId<1) throw Error('Invalid root, focus, or ID sequence.');
 for(const id of keys){
 const n=input.nodes[id];
 if(!/^[a-zA-Z0-9_-]{1,80}$/.test(id)||!n||n.id!==id||!['map','note','counter'].includes(n.kind)||typeof n.title!=='string'||!n.title.trim()||n.title.length>160||typeof n.body!=='string'||n.body.length>20000||!Array.isArray(n.children)||new Set(n.children).size!==n.children.length||n.children.some(c=>typeof c!=='string'||!own(c))) throw Error('Invalid place: '+id);
 if(n.kind==='counter'&&(!Number.isSafeInteger(n.value)||n.value<0)) throw Error('Invalid practice count.');
 }
 const visited=new Set(), active=new Set(), parents=new Map();
 function walk(id,depth){if(depth>100)throw Error('Garden is too deep.');if(active.has(id))throw Error('Circular maps are not supported.');if(visited.has(id))return;active.add(id);for(const c of input.nodes[id].children){if(parents.has(c))throw Error('A place must have one parent.');parents.set(c,id);walk(c,depth+1);}active.delete(id);visited.add(id);}
 walk(input.root,0);if(visited.size!==keys.length||parents.has(input.root))throw Error('Every place must belong to the root map.');
 return clone(input);
}
export function decode(text){if(typeof text!=='string'||text.length>2000000)throw Error('File exceeds the 2 MB limit.');return validate(JSON.parse(text));}
export function encode(g){return JSON.stringify(validate(g),null,2);}
export function visible(g){const out=[];function visit(id,depth,address){out.push({id,depth,address});if(depth<2)g.nodes[id].children.forEach((c,i)=>visit(c,depth+1,address?address+'.'+(i+1):String(i+1)));}visit(g.focus,0,'');return out;}
export function trail(g){const parent=new Map();for(const n of Object.values(g.nodes))for(const c of n.children)parent.set(c,n.id);const out=[];let id=g.focus;while(id){out.unshift(id);id=parent.get(id);}return out;}
export function apply(g,action){const s=validate(g),n=s.nodes[action.id??s.focus];if(!n)throw Error('Unknown place.');
 switch(action.type){
 case 'focus':s.focus=n.id;break;
 case 'add':{if(Object.keys(s.nodes).length>=2000)throw Error('Garden is full.');let id;do{id='n'+s.nextId++;}while(Object.prototype.hasOwnProperty.call(s.nodes,id));const kind=action.kind??'map';s.nodes[id]={id,title:action.title??'Untitled place',body:action.body??'',kind,children:[],...(kind==='counter'?{value:0}:{})};n.children.push(id);break;}
 case 'edit':n.title=action.title;n.body=action.body;break;
 case 'repeat':if(n.kind!=='counter')throw Error('Not a practice place.');n.value++;break;
 case 'remove':if(n.id===s.root)throw Error('The root cannot be removed.');{const ids=new Set();function collect(id){ids.add(id);s.nodes[id].children.forEach(collect);}collect(n.id);const parent=Object.values(s.nodes).find(p=>p.children.includes(n.id));parent.children=parent.children.filter(id=>id!==n.id);if(ids.has(s.focus))s.focus=parent.id;for(const id of ids)delete s.nodes[id];}break;
 default:throw Error('Unknown action.');
 }return validate(s);
}
