/* Run with Playwright, Python/openpyxl and a Chromium browser.
 * node maintenance/test_figures.cjs --browser <path>
 */
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {execFileSync}=require('node:child_process'),{pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
async function main(){
 const root=path.resolve(__dirname,'..'),temp=await fs.mkdtemp(path.join(os.tmpdir(),'fish-render-test-'));
 const out=path.join(temp,'report'),arg=process.argv.indexOf('--browser');
 execFileSync(process.env.PYTHON||'python',['-X','utf8','-B',path.join(root,'toolkit/tools/render_reviewed.py'),path.join(root,'toolkit/skill/assets/presentation-example.json'),'--output',out,'--stage','preview']);
 const browser=await chromium.launch({headless:true,...(arg>=0?{executablePath:process.argv[arg+1]}:{})});
 try{
  const page=await browser.newPage();await page.goto(pathToFileURL(path.join(out,'index.html')).href);
  const result=await page.evaluate(()=>{
   function bars(values){
    const raw=reportAPI.draw({id:'n',type:'bar',title:'Values',rows:values.map((value,i)=>({label:String(i),value}))});
    return [...new DOMParser().parseFromString(raw,'image/svg+xml').querySelectorAll('rect')]
     .filter(e=>e.getAttribute('height')==='14').map(e=>({x:+e.getAttribute('x'),w:+e.getAttribute('width')}));
   }
   const a=bars([-2,2]),n=bars([-2,-1]);
   const empty=reportAPI.draw({id:'empty',type:'bar',title:'Empty',rows:[]});
   return {mixed_signs:Math.abs(a[0].x+a[0].w-a[1].x)<1e-9&&Math.abs(a[0].w-a[1].w)<1e-9,
    negative_only:Math.abs(n[0].w-2*n[1].w)<1e-9,
    empty:empty.includes('暂无数值')&&!/NaN|Infinity/.test(empty)};
  });
  if(Object.values(result).some(v=>!v))throw Error(JSON.stringify(result));
  console.log(JSON.stringify(result));
 }finally{
  await browser.close();
  // temp is the exact directory returned by mkdtemp for this test.
  await fs.rm(temp,{recursive:true,force:true});
 }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
