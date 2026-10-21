/* Shared report components. Biology and field mappings belong to input files. */
(() => {
  "use strict";
  const {data:D, profile:P}=window.REPORT;
  const E=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const T=v=>Array.isArray(v)?v.map(T).join("\n"):v&&typeof v==="object"?v.text??JSON.stringify(v):String(v??"");
  const F=(r,k)=>k.split(".").reduce((v,p)=>v?.[p],r)??"";
  const M=(r,c)=>c.fields?c.fields.map(k=>T(F(r,k))).filter(Boolean).join(c.separator??"\n"):F(r,c.field);
  const para=v=>`<p>${E(T(v)).replace(/\n/g,"<br>")}</p>`;
  const safeURL=s=>/^https?:\/\//i.test(s||"")?s:"";
  const valueHTML=v=>v&&typeof v==="object"&&safeURL(v.url)?`<a href="${E(v.url)}" target="_blank" rel="noopener">${E(T(v))}</a>`:E(T(v)).replace(/\n/g,"<br>");
  const by=Object.fromEntries(D.chemicals.map(c=>[c.id,c]));
  const sources=Object.fromEntries(D.sources.map(c=>[c.id,c]));
  const panels=Object.fromEntries(D.panels.map(p=>[p.id,p]));
  const state={section:P.web.initial_section||P.web.sections[0].id,search:"",group:"",chemical:""};
  const normalizeSearch=s=>T(s).normalize("NFKC").toLowerCase().replace(/\s+/g,"");
  const searchFields=P.web.search_fields||["name","id","abbr","aliases","cas","group"];
  const selected=()=>D.chemicals.filter(c=>(!state.chemical||c.id===state.chemical)&&(!state.group||c.group===state.group)&&(!state.search||normalizeSearch(searchFields.map(k=>T(F(c,k))).join(" ")).includes(normalizeSearch(state.search))));
  const scoped=records=>{const ids=new Set(selected().map(c=>c.id));return records.filter(r=>!r.chemical_ids?.length||r.chemical_ids.some(id=>ids.has(id)));};
  const sourceLinks=ids=>(ids||[]).map(id=>sources[id]?`<a href="#" data-source="${E(id)}">${E(id)}</a>`:"").join(" / ");
  const blobDownload=(content,name,type)=>{const u=URL.createObjectURL(new Blob([content],{type})),a=document.createElement("a");a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);};
  function csv(rows){return "\ufeff"+rows.map(row=>row.map(v=>{let s=T(v);if(/^[=+@-]/.test(s)&&isNaN(Number(s)))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}).join(",")).join("\r\n");}
  function table(id,title,cols,rows,detail=false){
    return `<div class="rich-table" id="${E(id)}"><div class="table-head"><h3>${E(title)}</h3><button data-copy="${E(id)}">复制表格</button></div><div class="table-scroll"><table><thead><tr>${cols.map(c=>`<th>${E(c.label)}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr data-row-id="${E(r.id||"")}">${cols.map(c=>`<td>${detail&&c.detail_link?`<button class="link-button" data-chemical="${E(r.id)}">${E(T(M(r,c)))||"查看"}</button>`:valueHTML(M(r,c))}</td>`).join("")}</tr>`).join("")||`<tr><td colspan="${cols.length}">当前筛选没有记录。</td></tr>`}</tbody></table></div></div>`;
  }
  function detail(title,body){
    document.getElementById("detail-title").textContent=title;document.getElementById("detail-content").innerHTML=body;
    const d=document.getElementById("detail");if(!d.open)d.showModal();
  }
  function chemicalDetail(id){const c=by[id];if(c)detail(c.name,`<span class="pill">${E(c.group)}</span><h3>预测</h3>${para(c.prediction)}`+(c.details||[]).map(d=>`<h3>${E(d.label)}</h3>${para(d.text)}${sourceLinks(d.source_ids)}`).join(""));}
  function sourceDetail(id){const s=sources[id];if(s)detail(id+" · "+s.title,para(s.note||"")+(safeURL(s.url)?`<a href="${E(s.url)}" target="_blank" rel="noopener">查看来源</a>`:""));}
  function itemDetail(panel,id,type){const p=panels[panel],item=(type==="edge"?p.edges:p.nodes).find(x=>x.id===id);if(item)detail(item.label||item.id,para(item.detail||"")+(item.details||[]).map(d=>`<h3>${E(d.label)}</h3>${para(d.text)}`).join("")+sourceLinks(item.source_ids));}
  const theme=Object.assign({ink:"#22313b",muted:"#627079",line:"#dce3e6",accent:"#285e78",ligand:"#dcebf2",receptor:"#e9e3ef",process:"#f2f5f6",outcome:"#f3e6da"},P.web.theme);
  for(const k of ["ink","muted","line","accent"])document.documentElement.style.setProperty("--"+k,theme[k]);
  function svgStart(w,h,label){return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${E(label)}"><style>text{font-family:Arial,'Microsoft YaHei',sans-serif;fill:${theme.ink};font-size:13px}.small{font-size:11px;fill:${theme.muted}}.tap{cursor:pointer}.tap:focus{outline:2px solid ${theme.accent}}.tap:hover{filter:brightness(.92)}</style><rect width="${w}" height="${h}" fill="white"/>`;}
  function lines(x,y,value,width,options={}){
    const size=options.size||13,anchor=options.anchor||"start",out=[];let line="",used=0;
    for(const c of T(value)){const n=c.charCodeAt(0)>255?1.7:1;if(c==="\n"||used+n>width){out.push(line);line=c==="\n"?"":c;used=c==="\n"?0:n;}else{line+=c;used+=n;}}out.push(line);
    return `<text x="${x}" y="${y}" text-anchor="${anchor}" style="font-size:${size}px">${out.map((s,i)=>`<tspan x="${x}" dy="${i?size*1.5:0}">${E(s)}</tspan>`).join("")}</text>`;
  }
  function network(p){
    const w=p.width||820,h=p.height||480,lookup=Object.fromEntries(p.nodes.map((n,i)=>[n.id,{...n,x:(n.x??90+(i%4)*200)+(p.coordinate_origin==='top-left'?(n.w||128)/2:0),y:(n.y??65+Math.floor(i/4)*110)+(p.coordinate_origin==='top-left'?(n.h||42)/2:0)}]));
    let s=svgStart(w,h,p.title)+`<defs><marker id="${p.id}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="${theme.accent}"/></marker><marker id="${p.id}-stop" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="9" markerHeight="9" orient="auto"><path d="M7 0V10" stroke="${theme.ink}" stroke-width="1.5"/></marker></defs>`;
    for(const e of p.edges){
      const a=lookup[e.from],b=lookup[e.to],dx=b.x-a.x,dy=b.y-a.y;
      const trim=n=>Math.min((n.w||128)/2/(Math.abs(dx)||1),(n.h||42)/2/(Math.abs(dy)||1));
      const t1=trim(a),t2=trim(b),ax=a.x+dx*t1,ay=a.y+dy*t1,bx=b.x-dx*t2,byy=b.y-dy*t2;
      const path=e.points?`M${e.points.map(pt=>pt.join(",")).join(" L")}`:`M${ax},${ay} L${bx},${byy}`;
      const end=e.kind==="binding"?"":`marker-end="url(#${p.id}-${e.kind==="inhibition"?"stop":"arrow"})"`;
      s+=`<g class="tap" tabindex="0" role="button" aria-label="${E(e.label||e.id)}" data-panel="${p.id}" data-edge="${E(e.id)}"><path d="${path}" fill="none" stroke="transparent" stroke-width="15"/><path d="${path}" fill="none" stroke="${theme.accent}" stroke-width="1.6" ${e.kind==="indirect"?'stroke-dasharray="5 4"':""} ${end}/><title>${E(e.label||"查看关系")}</title></g>`;
      if(e.short_label)s+=lines(e.label_x??(ax+bx)/2+8,e.label_y??(ay+byy)/2-8,e.short_label,23,{size:11});
    }
    for(const n of Object.values(lookup)){
      const nw=n.w||128,nh=n.h||42;
      s+=`<g class="tap" tabindex="0" role="button" aria-label="${E(n.label)}" data-panel="${p.id}" data-node="${E(n.id)}"><rect x="${n.x-nw/2}" y="${n.y-nh/2}" width="${nw}" height="${nh}" rx="${n.kind==="ligand"?18:4}" fill="${theme[n.kind]||theme.process}" stroke="#91a6b2"/>${lines(n.x,n.y-(T(n.label).includes("\n")?5:0)+5,n.label,nw/8,{anchor:"middle",size:p.font_size||15})}<title>${E(n.label)}</title></g>`;
    }
    return s+"</svg>";
  }
  function matrix(p){
    const rows=scoped(p.rows),left=p.label_width||120,cw=p.column_width||145,rh=p.row_height||58,w=left+p.columns.length*cw+16,h=80+Math.max(1,rows.length)*rh;
    let s=svgStart(w,h,p.title);p.columns.forEach((c,j)=>{s+=lines(left+j*cw+9,23,c,cw/7,{size:12});});
    rows.forEach((r,i)=>{const y=65+i*rh;if(i%2===0)s+=`<rect x="0" y="${y-13}" width="${w}" height="${rh}" fill="#f6f8f9"/>`;
      s+=`<g class="tap" data-chemical="${E(r.chemical_ids?.[0]||"")}" tabindex="0" role="button" aria-label="${E(r.label)}">${lines(7,y+9,r.label,17,{size:12})}</g>`;
      r.values.forEach((v,j)=>{s+=lines(left+j*cw+9,y+6,v,cw/7,{size:12});});});
    if(!rows.length)s+=lines(20,88,"当前筛选没有记录。",40);
    return s+"</svg>";
  }
  function numeric(p){
    const rows=scoped(p.rows),w=p.width||720,left=p.label_width||185,right=100,top=34,rh=46,h=top+Math.max(1,rows.length)*rh+67;
    const vals=p.rows.flatMap(r=>[r.low,r.high,r.value].filter(v=>v!=null)),log=p.scale==="log",trans=v=>log?Math.log10(v):v;
    if(!vals.length)return svgStart(w,120,p.title)+lines(20,60,"暂无数值记录。",40)+"</svg>";
    let lo=p.domain?.[0]??Math.min(...vals),hi=p.domain?.[1]??Math.max(...vals);
    if(p.type==="bar"&&!log&&!p.domain){lo=Math.min(0,lo);hi=Math.max(0,hi);}lo=trans(lo);hi=trans(hi);if(hi===lo){lo-=.5;hi+=.5;}
    const x=v=>left+(trans(v)-lo)/(hi-lo)*(w-left-right);let s=svgStart(w,h,p.title);
    const baseline=log?left:Math.max(left,Math.min(w-right,x(0)));
    for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,xx=left+i/4*(w-left-right),label=log?Number((10**v).toPrecision(3)):Number(v.toPrecision(4));
      s+=`<path d="M${xx},${top-10}V${h-45}" stroke="${theme.line}"/><text x="${xx}" y="${h-25}" text-anchor="middle" class="small">${label}</text>`;}
    rows.forEach((r,i)=>{const y=top+i*rh+12;s+=`<g class="tap" data-chemical="${E(r.chemical_ids?.[0]||"")}" tabindex="0" role="button" aria-label="${E(r.label)}">${lines(8,y-3,r.label,left/7-3,{size:12})}`;
      if(r.low!=null&&r.high!=null)s+=`<path d="M${x(r.low)},${y}H${x(r.high)}" stroke="#7fa3b5" stroke-width="4"/><path d="M${x(r.low)},${y-5}V${y+5}M${x(r.high)},${y-5}V${y+5}" stroke="${theme.accent}"/>`;
      if(r.value!=null)s+=p.type==="bar"?`<rect x="${Math.min(baseline,x(r.value))}" y="${y-7}" width="${Math.abs(x(r.value)-baseline)}" height="14" fill="${theme.accent}"/>`:`<circle cx="${x(r.value)}" cy="${y}" r="4" fill="${theme.accent}"/>`;
      const lab=r.value??(r.low!=null?`${r.low}–${r.high}`:"无记录");s+=`<text x="${w-right+14}" y="${y+4}" class="small">${E(lab)}</text></g>`;});
    s+=`<text x="${(w+left-right)/2}" y="${h-3}" text-anchor="middle" class="small">${E(p.axis_label||p.unit||"")}</text>`;
    return s+"</svg>";
  }
  const scatterRows=p=>scoped(p.rows).filter(r=>r.x!=null&&r.value!=null&&(!p.size_required||r.size!=null));
  function scatter(p){
    const rows=scatterRows(p),all=p.rows.filter(r=>r.x!=null&&r.value!=null&&(!p.size_required||r.size!=null));
    if(!all.length)return svgStart(720,120,p.title)+lines(20,60,'暂无数值记录。',40)+'</svg>';
    const w=p.width||760,h=p.height||420,L=85,R=w-70,T=30,B=h-75;
    function axis(vals,domain,log,start,end){
      const tr=v=>log?Math.log10(v):v;let lo=domain?.[0]??Math.min(...vals),hi=domain?.[1]??Math.max(...vals);
      lo=tr(lo);hi=tr(hi);if(hi===lo){lo-=.5;hi+=.5;}
      if(!domain){const pad=(hi-lo)*.08;lo-=pad;hi+=pad;}
      return {at:v=>start+(tr(v)-lo)/(hi-lo)*(end-start),ticks:Array.from({length:5},(_,i)=>{const a=lo+(hi-lo)*i/4;return log?10**a:a;})};
    }
    const x=axis(all.map(r=>r.x),p.x_domain,p.x_scale==='log',L,R),y=axis(all.flatMap(r=>[r.value,r.low,r.high].filter(v=>v!=null)),p.y_domain,p.y_scale==='log',B,T);
    const maxSize=Math.max(1,...all.map(r=>r.size||0)),radius=v=>v==null?4:Math.max(2,Math.sqrt(v/maxSize)*14);
    let s=svgStart(w,h,p.title);
    for(const v of x.ticks)s+=`<path d="M${x.at(v)},${T}V${B}" stroke="${theme.line}"/><text x="${x.at(v)}" y="${B+22}" text-anchor="middle" class="small">${Number(v.toPrecision(3))}</text>`;
    for(const v of y.ticks)s+=`<path d="M${L},${y.at(v)}H${R}" stroke="${theme.line}"/><text x="${L-10}" y="${y.at(v)+4}" text-anchor="end" class="small">${Number(v.toPrecision(3))}</text>`;
    for(const r of rows){
      const xx=x.at(r.x),yy=y.at(r.value),rr=radius(r.size);
      s+=`<g class="tap" data-chemical="${E(r.chemical_ids?.[0]||'')}" tabindex="0" role="button" aria-label="${E(r.label)}">`;
      if(r.low!=null&&r.high!=null)s+=`<path d="M${xx},${y.at(r.low)}V${y.at(r.high)}" stroke="${theme.accent}" stroke-width="1.5"/>`;
      s+=`<circle cx="${xx}" cy="${yy}" r="${rr}" fill="${theme.ligand}" stroke="${theme.accent}"/><text x="${xx+(r.label_dx??rr+6)}" y="${yy+(r.label_dy??-6)}" class="small">${E(r.label)}</text><title>${E(r.note||r.label)}</title></g>`;
    }
    s+=`<text x="${(L+R)/2}" y="${h-15}" text-anchor="middle">${E(p.x_label||'x')}</text><text transform="translate(17 ${(T+B)/2}) rotate(-90)" text-anchor="middle">${E(p.y_label||'value')}</text>`;
    if(p.size_label)s+=`<text x="${R}" y="18" text-anchor="end" class="small">${E(p.size_label)} · 最大点 ${maxSize}</text>`;
    return s+'</svg>';
  }
  function heatmap(p){
    const rows=scoped(p.rows),left=p.label_width||100,cw=p.column_width||76,rh=p.row_height||42,w=left+p.columns.length*cw+18,h=95+Math.max(1,rows.length)*rh;
    const values=p.rows.flatMap(r=>r.values.filter(v=>typeof v==='number')),lo=p.domain?.[0]??Math.min(...values),hi=p.domain?.[1]??Math.max(...values);
    const color=v=>{const t=Math.max(0,Math.min(1,(v-lo)/(hi-lo||1)));return `rgb(${Math.round(246-160*t)},${Math.round(249-117*t)},${Math.round(250-90*t)})`;};
    let s=svgStart(w,h,p.title);
    p.columns.forEach((c,j)=>{s+=lines(left+j*cw+cw/2,23,c,cw/7,{size:11,anchor:'middle'});});
    rows.forEach((r,i)=>{const y=58+i*rh;s+=`<g class="tap" data-chemical="${E(r.chemical_ids?.[0]||'')}" tabindex="0" role="button" aria-label="${E(r.label)}">${lines(5,y+rh/2+4,r.label,left/7,{size:12})}`;
      r.values.forEach((v,j)=>{const x=left+j*cw;s+=`<rect x="${x}" y="${y}" width="${cw}" height="${rh}" fill="${typeof v==='number'?color(v):'#f6f8f9'}" stroke="white"/><text x="${x+cw/2}" y="${y+rh/2+4}" text-anchor="middle" style="font-size:11px;fill:${typeof v==='number'&&(v-lo)/(hi-lo||1)>.65?'white':theme.ink}">${E(typeof v==='number'?Number(v.toPrecision(p.precision||3)):v??'—')}</text>`;});s+='</g>';});
    return s+'</svg>';
  }
  function draw(p){return ({network,matrix,interval:numeric,bar:numeric,scatter,heatmap})[p.type]?.(p)||"";}
  function panelHTML(p){
    const graphic=p.type==="image"?`<img src="${E(p.asset)}" alt="${E(p.title)}">`:draw(p);
    return `<figure class="panel ${p.wide?"wide-panel":""}" id="panel-${p.id}"><div class="table-head"><h3>${E(p.title)}</h3><button data-zoom="${p.id}">放大</button></div><div class="graphic" data-graphic="${p.id}">${graphic}</div><figcaption>${E(p.caption||"")} ${sourceLinks(p.source_ids)}</figcaption><div class="panel-exports">${p.type!=="image"?`<button data-export="${p.id}" data-format="svg">SVG</button><button data-export="${p.id}" data-format="png">PNG</button><button data-export="${p.id}" data-format="pdf">打印 / PDF</button><button data-export="${p.id}" data-format="csv">数据 CSV</button>`:`<a href="${E(p.asset)}" download>下载原图</a>`}</div></figure>`;
  }
  function panelRows(p){
    if(p.type==="network")return [["kind","id","label","from","to","relation","detail","sources"],...p.nodes.map(n=>["node",n.id,n.label,"","","",n.detail||"",n.source_ids||[]]),...p.edges.map(e=>["edge",e.id,e.label,e.from,e.to,e.kind,e.detail||"",e.source_ids||[]])];
    if(p.type==="matrix"||p.type==="heatmap")return [["物质",...p.columns],...scoped(p.rows).map(r=>[r.label,...r.values])];
    if(p.type==="scatter")return [["对象","x","low","value","high","size","source"],...scatterRows(p).map(r=>[r.label,r.x,r.low,r.value,r.high,r.size,r.source_ids||[]])];
    return [["对象","low","value","high","unit","source"],...scoped(p.rows||[]).map(r=>[r.label,r.low,r.value,r.high,p.unit||"",r.source_ids||[]])];
  }
  async function exportPanel(id,fmt){
    const p=panels[id],svg=draw(p),name=`${id}-${state.chemical||state.group||"all"}`;
    if(fmt==="csv")return blobDownload(csv(panelRows(p)),name+".csv","text/csv;charset=utf-8");
    if(fmt==="svg")return blobDownload(svg,name+".svg","image/svg+xml");
    if(fmt==="png"){
      const img=new Image(),url=URL.createObjectURL(new Blob([svg],{type:"image/svg+xml"}));
      try{await new Promise((res,rej)=>{img.onload=res;img.onerror=rej;img.src=url;});const c=document.createElement("canvas");c.width=img.naturalWidth*2;c.height=img.naturalHeight*2;c.getContext("2d").drawImage(img,0,0,c.width,c.height);const a=document.createElement("a");a.download=name+".png";a.href=c.toDataURL("image/png");a.click();}finally{URL.revokeObjectURL(url);}return;
    }
    const win=window.open("","_blank");if(!win){status("请允许打开打印窗口。");return;}
    win.document.write(`<!doctype html><html><head><title>${E(p.title)}</title><style>@page{size:landscape;margin:15mm}body{font:14px Arial,'Microsoft YaHei'}svg{max-width:100%;max-height:75vh;width:auto;height:auto}h1{font-size:18px}</style></head><body><h1>${E(p.title)}</h1>${svg}<p>${E(p.caption||"")}</p></body></html>`);
    win.document.close();win.focus();setTimeout(()=>win.print(),300);
  }
  function status(msg){const s=document.getElementById("status");s.textContent=msg;s.style.display="block";setTimeout(()=>s.style.display="none",2200);}
  async function copy(id){
    const clone=document.getElementById(id).cloneNode(true);clone.querySelectorAll("button,.panel-exports,input,select,svg,dialog").forEach(n=>n.remove());
    clone.querySelectorAll("table").forEach(t=>{t.style.borderCollapse="collapse";t.style.width="100%";});clone.querySelectorAll("th,td").forEach(c=>{c.style.border="1px solid #c9d3d9";c.style.padding="7px";c.style.verticalAlign="top";});
    try{await navigator.clipboard.write([new ClipboardItem({"text/html":new Blob([clone.innerHTML],{type:"text/html"}),"text/plain":new Blob([clone.textContent],{type:"text/plain"})})]);status("已复制");}
    catch{const holder=document.createElement("div");holder.className="copy-payload";holder.innerHTML=clone.innerHTML;document.body.append(holder);const range=document.createRange();range.selectNodeContents(holder);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);const ok=document.execCommand("copy");holder.remove();selection.removeAllRanges();status(ok?"已复制":"复制未完成，请选择表格后按 Ctrl+C");}
  }
  function drawContent(){
    for(const sec of P.web.sections){const el=document.getElementById("content-"+sec.id);let html="";
      for(const b of sec.blocks){
        if(b.kind==="text")html+=(F(D,b.field)||[]).map(para).join("");
        if(b.kind==="chemicals")html+=table("chemical-table",b.title||"全家族比较",b.columns,selected(),true);
        if(b.kind==="table"){const t=table(b.id,b.title,b.columns,scoped(F(D,b.collection)||[]));html+=b.collapsed?`<details class="more"><summary>${E(b.title)}</summary>${t}</details>`:t;}
        if(b.kind==="panels")html+=`<div class="panel-grid">${D.panels.filter(p=>p.section===sec.id).map(panelHTML).join("")}</div>`;
        if(b.kind==="details")html+=selected().map(c=>`<details class="more"><summary>${E(c.name)} · ${E(c.group)}</summary>${para(c.prediction)}<button data-chemical="${E(c.id)}">查看完整分析</button></details>`).join("");
      }el.innerHTML=html;
    }document.getElementById("count").textContent=`${selected().length} / ${D.chemicals.length} 种`;
  }
  function switchTab(id){if(!P.web.sections.some(s=>s.id===id))id=P.web.sections[0].id;state.section=id;document.querySelectorAll(".page").forEach(e=>e.hidden=e.id!==id);document.querySelectorAll("[data-tab]").forEach(b=>b.setAttribute("aria-selected",String(b.dataset.tab===id)));history.replaceState(null,"","#"+id);}
  document.getElementById("title").textContent=D.title;document.getElementById("context").textContent=`${D.context||""} · ${D.analysis_version}`;
  document.getElementById("tabs").innerHTML=P.web.sections.map(s=>`<button role="tab" data-tab="${E(s.id)}" aria-controls="${E(s.id)}">${E(s.title)}</button>`).join("");
  document.getElementById("pages").innerHTML=P.web.sections.map(s=>`<section id="${E(s.id)}" class="page" role="tabpanel"><div class="section-actions"><button data-copy="content-${E(s.id)}">复制正文与表格</button></div><article id="content-${E(s.id)}"></article></section>`).join("");
  document.getElementById("group-filter").innerHTML=`<option value="">全部分组</option>`+[...new Set(D.chemicals.map(c=>c.group))].map(g=>`<option>${E(g)}</option>`).join("");
  document.getElementById("chemical-filter").innerHTML=`<option value="">全部物质</option>`+D.chemicals.map(c=>`<option value="${E(c.id)}">${E(c.name)}</option>`).join("");
  for(const [id,key,event] of [["search","search","input"],["group-filter","group","change"],["chemical-filter","chemical","change"]])document.getElementById(id).addEventListener(event,e=>{state[key]=e.target.value;drawContent();});
  document.addEventListener("click",async e=>{
    const b=e.target.closest("button,a,[data-node],[data-edge],[data-chemical]");if(!b)return;
    if(b.dataset.tab)switchTab(b.dataset.tab);
    if(b.dataset.chemical){e.preventDefault();chemicalDetail(b.dataset.chemical);}
    if(b.dataset.source){e.preventDefault();sourceDetail(b.dataset.source);}
    if(b.dataset.node)itemDetail(b.dataset.panel,b.dataset.node,"node");
    if(b.dataset.edge)itemDetail(b.dataset.panel,b.dataset.edge,"edge");
    if(b.dataset.close)document.getElementById(b.dataset.close).close();
    if(b.dataset.copy)await copy(b.dataset.copy);
    if(b.dataset.export)await exportPanel(b.dataset.export,b.dataset.format);
    if(b.dataset.zoom){const p=panels[b.dataset.zoom];document.getElementById("zoom-title").textContent=p.title;document.getElementById("zoom-content").innerHTML=p.type==="image"?`<img src="${E(p.asset)}" alt="${E(p.title)}">`:draw(p);document.getElementById("zoom").showModal();}
    if(b.id==="reset"){state.search=state.group=state.chemical="";["search","group-filter","chemical-filter"].forEach(id=>document.getElementById(id).value="");drawContent();}
    if(b.id==="export-family")blobDownload(csv([P.web.family_columns.map(c=>c.label),...selected().map(r=>P.web.family_columns.map(c=>M(r,c)))]),"family-filtered.csv","text/csv;charset=utf-8");
  });
  document.addEventListener("keydown",e=>{if((e.key==="Enter"||e.key===" ")&&e.target.matches("svg [role=button]")){e.preventDefault();e.target.dispatchEvent(new MouseEvent("click",{bubbles:true}));}});
  window.addEventListener("hashchange",()=>switchTab(location.hash.slice(1)));
  window.addEventListener("load",()=>requestAnimationFrame(()=>requestAnimationFrame(()=>window.scrollTo(0,0))));
  drawContent();switchTab(location.hash.slice(1)||state.section);
  window.reportAPI={draw,panels,selected,scoped,panelRows,panelCSV:p=>csv(panelRows(p)),state,refresh:drawContent,switchTab,exportPanel};
})();
