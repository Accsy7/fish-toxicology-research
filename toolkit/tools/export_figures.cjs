/* Optional offline figure files, using exactly the report's browser renderer.
 * Requires Playwright and a Chromium browser; the HTML itself has no Node dependency.
 */
const fs=require("node:fs/promises"),path=require("node:path"),{pathToFileURL}=require("node:url");
const {chromium}=require("playwright");
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function main(){
 const dir=path.resolve(process.argv[2]),browserArg=process.argv.indexOf("--browser");
 const browser=await chromium.launch({headless:true,...(browserArg>=0?{executablePath:process.argv[browserArg+1]}:{})});
 const manifest=[];
 try{
  const page=await browser.newPage({viewport:{width:1200,height:1000},deviceScaleFactor:2});
  await page.goto(pathToFileURL(path.join(dir,"index.html")).href);
  await page.waitForFunction(()=>window.reportAPI);
  const figures=await page.evaluate(()=>Object.values(window.reportAPI.panels).filter(p=>p.type!=="image").map(p=>({id:p.id,title:p.title,caption:p.caption,svg:window.reportAPI.draw(p),rows:window.reportAPI.panelRows(p),csv:window.reportAPI.panelCSV(p)})));
  await fs.mkdir(path.join(dir,"figures"),{recursive:true});
  for(const f of figures){
   const dims=/viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(f.svg),w=Number(dims[1]),h=Number(dims[2]);
   const exported=f.svg.replace(/width="[\d.]+" height="[\d.]+"/,'width="180mm" height="'+(180*h/w).toFixed(3)+'mm"');
   await fs.writeFile(path.join(dir,"figures",f.id+".svg"),exported);
   await fs.writeFile(path.join(dir,"figures",f.id+".csv"),f.csv);
   const art=await browser.newPage({viewport:{width:900,height:1200},deviceScaleFactor:2});
   await art.setContent('<!doctype html><html><head><meta charset="utf-8"><style>@page{size:A4;margin:15mm}body{margin:0;background:white;font:13px Arial,"Microsoft YaHei"}h1{font-size:17px}svg{display:block;width:180mm;height:auto}p{max-width:180mm;line-height:1.7}</style></head><body><h1>'+esc(f.title)+'</h1>'+exported+'<p>'+esc(f.caption)+'</p></body></html>');
   await art.locator("svg").screenshot({path:path.join(dir,"figures",f.id+".png")});
   await art.pdf({path:path.join(dir,"figures",f.id+".pdf"),printBackground:true,preferCSSPageSize:true});
   await art.close();manifest.push({id:f.id,width_mm:180,rows:f.rows.length-1,formats:["svg","png","pdf","csv"]});
  }
 }finally{await browser.close();}
 await fs.writeFile(path.join(dir,"figure-files.json"),JSON.stringify(manifest,null,2));
 console.log(JSON.stringify(manifest));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
