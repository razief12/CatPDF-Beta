// Pure page-list operations shared by UI and regression tests.
(function(root){
function change(items,action,i,j){const a=items.map(x=>({...x}));if(action==='reverse')return a.reverse();if(action==='blank'){const ref=a[i]||a[0];a.splice(i+1,0,{page:null,width:ref?.width||595.28,height:ref?.height||841.89,rotation:0});}else if(i>=0&&i<a.length){if(action==='delete'&&a.length>1)a.splice(i,1);if(action==='duplicate')a.splice(i+1,0,{...a[i]});if(action==='rotate')a[i].rotation=(a[i].rotation+90)%360;if(action==='move'&&j>=0&&j<a.length)a.splice(j,0,a.splice(i,1)[0]);}return a;}
root.CatOrganizeChange=change;
})(typeof globalThis!=='undefined'?globalThis:this);
