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
