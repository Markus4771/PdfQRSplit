"""Server-side PDF editor support. Does not publish to DATEV."""
import base64
import html
import re
from pathlib import Path

def page_plan(raw, count):
    if not isinstance(raw,str) or len(raw)>24000 or not raw:
        raise ValueError("Seitenplan fehlt oder ist zu lang")
    result=[]
    seen=set()
    for item in raw.split(","):
        match=re.fullmatch(r"([1-9][0-9]*):(0|90|180|270)",item)
        if not match:raise ValueError("Ungültiger Seitenplan")
        page,rotation=map(int,match.groups())
        if page>count or page in seen:raise ValueError("Seitenzahl ungültig oder doppelt")
        seen.add(page)
        result.append((page-1,rotation))
    if not result or len(result)>3000:raise ValueError("Keine gültigen Seiten")
    return result

def thumbnails(con,signature,share_root,archive_root,limit=80):
    import fitz
    from review_pdf import source_for_case
    source=source_for_case(con,signature,share_root,archive_root)
    with fitz.open(source) as doc:
        if doc.needs_pass:raise ValueError("Passwortgeschütztes PDF")
        if doc.page_count<1 or doc.page_count>limit:
            raise ValueError("Interaktiver Editor unterstützt maximal %s Seiten je Dokument"%limit)
        result=[]
        for idx,page in enumerate(doc):
            pix=page.get_pixmap(matrix=fitz.Matrix(.45,.45),alpha=False)
            result.append((idx+1,base64.b64encode(pix.tobytes("png")).decode("ascii")))
        return result

def editor_html(signature,images):
    sig=html.escape(signature,quote=True)
    blocks=[]
    for num,png in images:
        blocks.append('<div class="sheet" data-page="%d" data-rotation="0"><img loading="lazy" alt="Seite %d" src="data:image/png;base64,%s"><div>Seite %d</div><button type="button" class="up">↑</button><button type="button" class="down">↓</button><button type="button" class="rotate">Drehen 90°</button><label><input type="checkbox" class="keep" checked> Behalten</label><span class="angle">0°</span></div>'%(num,num,png,num))
    script="""<script>
    const container=document.getElementById('sheets');
    container.addEventListener('click',function(e){
      const tile=e.target.closest('.sheet');if(!tile)return;
      if(e.target.classList.contains('up')&&tile.previousElementSibling)container.insertBefore(tile,tile.previousElementSibling);
      if(e.target.classList.contains('down')&&tile.nextElementSibling)container.insertBefore(tile.nextElementSibling,tile);
      if(e.target.classList.contains('rotate')){
        let r=(Number(tile.dataset.rotation)+90)%360;tile.dataset.rotation=String(r);
        tile.querySelector('.angle').textContent=r+'°';
        tile.querySelector('img').style.transform='rotate('+r+'deg)';
      }
    });
    document.getElementById('editor-form').addEventListener('submit',function(e){
      const rows=[...container.querySelectorAll('.sheet')].filter(x=>x.querySelector('.keep').checked);
      if(!rows.length){e.preventDefault();alert('Mindestens eine Seite behalten');return;}
      document.getElementById('plan').value=rows.map(x=>x.dataset.page+':'+x.dataset.rotation).join(',');
    });
    </script>"""
    return ('<header><h1>PDF-Seitenkorrektur</h1><a href="/review">Zur Prüfwarteschlange</a></header>'
       '<section><p>Seiten über Pfeile verschieben, drehen oder abwählen. Original bleibt unverändert; keine DATEV-Übertragung.</p>'
       '<form id="editor-form" method="post" action="/review-editor-save"><input type="hidden" name="signature" value="'+sig+'">'
       '<input type="hidden" name="plan" id="plan"><div id="sheets" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px">'
       +''.join(blocks)+'</div><button type="submit">Korrekturentwurf speichern</button></form></section>'
       '<style>.sheet{padding:9px;border:1px solid #999;border-radius:6px}.sheet img{width:100%;height:210px;object-fit:contain}.sheet button{margin:4px}</style>'+script)
